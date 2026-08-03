"""Audit log routes (super admin only)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func

from database import get_db
from models.audit import AuditLog
from middleware.auth_middleware import require_super

router = APIRouter()


@router.get("")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: str = Query(None),
    end_date: str = Query(None),
    operator_name: str = Query(None),
    action: str = Query(None),
    db=Depends(get_db),
    _current_user=Depends(require_super),
):
    """List audit logs with optional date and operator filters."""
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)

    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
        count_query = count_query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)
        count_query = count_query.where(AuditLog.created_at <= end_date)
    if operator_name:
        query = query.where(AuditLog.operator_name.contains(operator_name))
        count_query = count_query.where(AuditLog.operator_name.contains(operator_name))
    if action:
        query = query.where(AuditLog.action.contains(action))
        count_query = count_query.where(AuditLog.action.contains(action))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    result = await db.execute(
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()

    items = []
    for log in logs:
        items.append({
            "id": log.id,
            "operator_name": log.operator_name or "",
            "operator_id": log.operator_id,
            "action": log.action or "",
            "target": log.target or "",
            "ip_address": log.ip_address or "",
            "is_ai_call": log.is_ai_call or False,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }
