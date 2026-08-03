"""Error log routes for viewing and repairing logged errors."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from typing import Optional

from database import get_db
from models.error_log import ErrorLog
from middleware.auth_middleware import get_current_user, require_super

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────

class ErrorLogEntry(BaseModel):
    endpoint: str = ""
    method: str = "GET"
    error_type: str = ""
    error_message: str = ""
    status_code: int = 500
    stack_trace: str = ""
    request_body: str = ""
    user_id: Optional[int] = None
    user_name: str = ""
    source: str = "frontend"

    class Config:
        # Allow extra fields from frontend that we don't need
        extra = "ignore"


class RepairRequest(BaseModel):
    repair_note: str = ""


# ── Endpoints ──────────────────────────────────────────────────────────

@router.get("")
async def list_error_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    repair: Optional[bool] = Query(None),         # filter by repair status
    source: Optional[str] = Query(None),           # "backend" or "frontend"
    error_type: Optional[str] = Query(None),
    endpoint: Optional[str] = Query(None),
    db=Depends(get_db),
    _current_user=Depends(require_super),
):
    """List error logs with filtering. Super admin only."""
    query = select(ErrorLog)
    count_q = select(func.count()).select_from(ErrorLog)

    if repair is not None:
        query = query.where(ErrorLog.repair == repair)
        count_q = count_q.where(ErrorLog.repair == repair)
    if source:
        query = query.where(ErrorLog.source == source)
        count_q = count_q.where(ErrorLog.source == source)
    if error_type:
        query = query.where(ErrorLog.error_type.contains(error_type))
        count_q = count_q.where(ErrorLog.error_type.contains(error_type))
    if endpoint:
        query = query.where(ErrorLog.endpoint.contains(endpoint))
        count_q = count_q.where(ErrorLog.endpoint.contains(endpoint))

    total_result = await db.execute(count_q)
    total = total_result.scalar()

    result = await db.execute(
        query.order_by(desc(ErrorLog.timestamp))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()

    items = []
    for log in logs:
        items.append({
            "id": log.id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "endpoint": log.endpoint,
            "method": log.method,
            "error_type": log.error_type,
            "error_message": log.error_message,
            "status_code": log.status_code,
            "stack_trace": log.stack_trace,
            "request_body": log.request_body,
            "user_id": log.user_id,
            "user_name": log.user_name,
            "source": log.source,
            "repair": log.repair,
            "repair_note": log.repair_note,
            "repaired_at": log.repaired_at.isoformat() if log.repaired_at else None,
            "repaired_by": log.repaired_by,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


@router.put("/{log_id}/repair")
async def mark_repaired(
    log_id: int,
    body: RepairRequest,
    db=Depends(get_db),
    current_user=Depends(require_super),
):
    """Mark an error log as repaired. Super admin or Agent only."""
    result = await db.execute(select(ErrorLog).where(ErrorLog.id == log_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="日志不存在")

    log.repair = True
    log.repair_note = body.repair_note
    log.repaired_at = datetime.utcnow()
    log.repaired_by = current_user.name

    await db.flush()
    return {"id": log.id, "repair": True, "message": "已标记为已修复"}


@router.post("")
async def report_error(
    body: ErrorLogEntry,
    request: Request,
    db=Depends(get_db),
):
    """Report an error from frontend or backend. No auth required (frontend may not have valid token)."""
    log = ErrorLog(
        timestamp=datetime.utcnow(),
        endpoint=body.endpoint,
        method=body.method,
        error_type=body.error_type,
        error_message=body.error_message,
        status_code=body.status_code,
        stack_trace=body.stack_trace,
        request_body=body.request_body,
        user_id=body.user_id,
        user_name=body.user_name,
        source=body.source,
        repair=False,
    )
    db.add(log)
    await db.flush()
    return {"id": log.id, "message": "错误已记录"}


@router.get("/stats")
async def error_stats(
    db=Depends(get_db),
    _current_user=Depends(require_super),
):
    """Get error statistics summary."""
    total_result = await db.execute(select(func.count()).select_from(ErrorLog))
    total = total_result.scalar()

    unrepaired_result = await db.execute(
        select(func.count()).select_from(ErrorLog).where(ErrorLog.repair == False)
    )
    unrepaired = unrepaired_result.scalar()

    backend_result = await db.execute(
        select(func.count()).select_from(ErrorLog).where(ErrorLog.source == "backend")
    )
    backend_count = backend_result.scalar()

    frontend_result = await db.execute(
        select(func.count()).select_from(ErrorLog).where(ErrorLog.source == "frontend")
    )
    frontend_count = frontend_result.scalar()

    return {
        "total": total,
        "unrepaired": unrepaired,
        "backend": backend_count,
        "frontend": frontend_count,
    }
