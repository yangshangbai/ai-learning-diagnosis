"""标签接口。

端点：
  GET    /api/v1/tags         列表（q 过滤）
  POST   /api/v1/tags         创建（name 唯一）
  PUT    /api/v1/tags/{id}    更新
  DELETE /api/v1/tags/{id}    删除（同时从所有题目 tags 数组中移除）
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.errors import NotFoundError, ConflictError
from ..core.logging import logger
from ..core.security import Principal, require_auth, require_permission
from ..schemas.tag import TagCreate, TagOut, TagUpdate

router = APIRouter(prefix="/api/v1/tags", tags=["tag"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=List[TagOut])
def list_tags(
    q: Optional[str] = None,
    _: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    query = db.query(models.Tag)
    if q:
        query = query.filter(models.Tag.name.ilike(f"%{q}%"))
    rows = query.order_by(models.Tag.id).all()
    return [TagOut.model_validate(r) for r in rows]


@router.post("", response_model=TagOut, status_code=201)
def create_tag(
    body: TagCreate,
    _: Principal = Depends(require_permission("system", "add")),
    db: Session = Depends(get_db),
):
    exist = db.query(models.Tag).filter(models.Tag.name == body.name).first()
    if exist:
        raise ConflictError(f"标签「{body.name}」已存在")
    row = models.Tag(name=body.name, color=body.color)
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("tag_created", extra={"id": row.id, "tag_name": row.name})
    return TagOut.model_validate(row)


@router.put("/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: int,
    body: TagUpdate,
    _: Principal = Depends(require_permission("system", "edit")),
    db: Session = Depends(get_db),
):
    row = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not row:
        raise NotFoundError("标签", tag_id)
    if body.name != row.name:
        dup = db.query(models.Tag).filter(models.Tag.name == body.name, models.Tag.id != tag_id).first()
        if dup:
            raise ConflictError(f"标签「{body.name}」已存在")
    row.name = body.name
    row.color = body.color
    db.commit()
    db.refresh(row)
    return TagOut.model_validate(row)


@router.delete("/{tag_id}")
def delete_tag(
    tag_id: int,
    _: Principal = Depends(require_permission("system", "delete")),
    db: Session = Depends(get_db),
):
    row = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not row:
        raise NotFoundError("标签", tag_id)
    sid = str(tag_id)
    # 同时从所有题目的 tags 数组中移除该标签，避免脏引用
    affected = 0
    for q in db.query(models.Question).all():
        cur = [str(t) for t in (q.tags or [])]
        if sid in cur:
            q.tags = [t for t in cur if t != sid]
            affected += 1
    db.delete(row)
    db.commit()
    logger.info("tag_deleted", extra={"id": tag_id, "affected_questions": affected})
    return {"code": 0, "message": "deleted", "data": {"affected_questions": affected}}
