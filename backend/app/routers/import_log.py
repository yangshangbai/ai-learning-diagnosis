"""导入日志接口：题目批量导入历史记录。

端点：
  GET  /api/v1/import-logs  列表（分页，最新在前）
  POST /api/v1/import-logs  记录一次导入（docx/OCR/教研云落库后由前端调用）
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.logging import logger
from ..core.security import Principal, require_auth, require_permission
from ..schemas.import_log import ImportLogOut, PaginatedImportLog

router = APIRouter(prefix="/api/v1/import-logs", tags=["import-log"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ImportLogCreate(BaseModel):
    file_name: Optional[str] = None
    format: Optional[str] = None
    total_questions: int = 0
    success_count: int = 0
    fail_count: int = 0
    status: str = "completed"


@router.post("", response_model=ImportLogOut, status_code=201)
def create_import_log(
    body: ImportLogCreate,
    principal: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """记录一次导入历史（前端在题目落库成功后调用）。"""
    log = models.ImportLog(
        file_name=body.file_name,
        format=body.format,
        total_questions=body.total_questions,
        success_count=body.success_count,
        fail_count=body.fail_count,
        status=body.status,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    logger.info("import_log_created", extra={"id": log.id, "file": body.file_name, "ok": body.success_count})
    return ImportLogOut.model_validate(log)


@router.get("", response_model=PaginatedImportLog)
def list_import_logs(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    _: Principal = Depends(require_permission("sync","view")),
    db: Session = Depends(get_db),
):
    query = db.query(models.ImportLog)
    if status:
        query = query.filter(models.ImportLog.status == status)
    total = query.count()
    rows = (
        query.order_by(desc(models.ImportLog.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedImportLog(
        items=[ImportLogOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
