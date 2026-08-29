"""系统日志模块接口。

端点：
  POST   /api/v1/system-logs           前端/后端错误上报（允许匿名，前端错误可在登录前发生）
  GET    /api/v1/system-logs           列表（分页+筛选，仅管理员）
  GET    /api/v1/system-logs/{id}      详情（仅管理员）
  PATCH  /api/v1/system-logs/{id}/repair  标记修复/取消修复（仅管理员，写 repaired 标记）
  DELETE /api/v1/system-logs/{id}      删除（仅管理员）

字段对齐：前端上报 body == SystemLogCreate；响应 == SystemLogOut。
"""
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.errors import NotFoundError, ValidationError
from ..core.security import Principal, get_current_user, require_permission
from ..schemas.system_log import (
    PaginatedSystemLog,
    SystemLogCreate,
    SystemLogOut,
    SystemLogRepair,
)

router = APIRouter(prefix="/api/v1/system-logs", tags=["system-log"])

_LEVELS = {"ERROR", "WARNING", "INFO", "DEBUG"}
_SOURCES = {"frontend", "backend"}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=SystemLogOut)
def report_log(
    body: SystemLogCreate,
    db: Session = Depends(get_db),
    principal: Optional[Principal] = Depends(get_current_user),
):
    if not body.message or not body.message.strip():
        raise ValidationError("message 不能为空")
    if body.source not in _SOURCES:
        raise ValidationError("source 仅允许 frontend/backend")
    if body.level not in _LEVELS:
        raise ValidationError("level 仅允许 ERROR/WARNING/INFO/DEBUG")

    row = models.SystemLog(
        level=body.level,
        source=body.source,
        module=body.module,
        message=body.message[:4000],
        detail=body.detail,
        traceback=body.traceback,
        url=body.url,
        request_id=body.request_id,
        user_id=principal.user_id if principal else None,
        username=principal.name if principal else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return SystemLogOut.model_validate(row)


@router.get("", response_model=PaginatedSystemLog)
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    level: Optional[str] = None,
    source: Optional[str] = None,
    repaired: Optional[bool] = None,
    module: Optional[str] = None,
    q: Optional[str] = None,
    _: Principal = Depends(require_permission("system", "view")),
    db: Session = Depends(get_db),
):
    query = db.query(models.SystemLog)
    if level:
        query = query.filter(models.SystemLog.level == level)
    if source:
        query = query.filter(models.SystemLog.source == source)
    if repaired is not None:
        query = query.filter(models.SystemLog.repaired == repaired)
    if module:
        query = query.filter(models.SystemLog.module == module)
    if q:
        query = query.filter(models.SystemLog.message.ilike(f"%{q}%"))

    total = query.count()
    rows = (
        query.order_by(desc(models.SystemLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedSystemLog(
        items=[SystemLogOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{log_id}", response_model=SystemLogOut)
def get_log(
    log_id: int, _: Principal = Depends(require_permission("system", "view")), db: Session = Depends(get_db)
):
    row = db.query(models.SystemLog).filter(models.SystemLog.id == log_id).first()
    if not row:
        raise NotFoundError("系统日志", log_id)
    return SystemLogOut.model_validate(row)


@router.patch("/{log_id}/repair", response_model=SystemLogOut)
def repair_log(
    log_id: int,
    body: SystemLogRepair,
    principal: Principal = Depends(require_permission("system", "edit")),
    db: Session = Depends(get_db),
):
    row = db.query(models.SystemLog).filter(models.SystemLog.id == log_id).first()
    if not row:
        raise NotFoundError("系统日志", log_id)
    row.repaired = body.repaired
    if body.repaired:
        row.repaired_at = datetime.datetime.now(datetime.timezone.utc)
        row.repaired_by = principal.user_id
        row.repaired_note = body.repaired_note
    else:
        row.repaired_at = None
        row.repaired_by = None
        row.repaired_note = None
    db.commit()
    db.refresh(row)
    return SystemLogOut.model_validate(row)


@router.delete("/{log_id}")
def delete_log(
    log_id: int, _: Principal = Depends(require_permission("system", "delete")), db: Session = Depends(get_db)
):
    row = db.query(models.SystemLog).filter(models.SystemLog.id == log_id).first()
    if not row:
        raise NotFoundError("系统日志", log_id)
    db.delete(row)
    db.commit()
    return {"code": 0, "message": "deleted", "data": None}
