"""组卷草稿接口（按用户隔离）。

端点：
  GET  /api/v1/paper-drafts   获取当前用户草稿（已选题目 id 列表）
  POST /api/v1/paper-drafts   保存草稿（body: {questions: [id, ...]}，按 user_id 覆盖）
"""
import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.security import Principal, require_auth, require_permission

router = APIRouter(prefix="/api/v1/paper-drafts", tags=["paper-draft"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PaperDraftIn(BaseModel):
    questions: List[str] = []


@router.get("")
def get_draft(
    principal: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    row = db.query(models.PaperDraft).filter(models.PaperDraft.user_id == principal.user_id).first()
    return {"code": 0, "message": "ok",
            "data": {"questions": row.questions or [] if row else []}}


@router.post("")
def save_draft(
    body: PaperDraftIn,
    _: Principal = Depends(require_permission("paper", "add")),
    db: Session = Depends(get_db),
):
    row = db.query(models.PaperDraft).filter(models.PaperDraft.user_id == principal.user_id).first()
    if row is None:
        row = models.PaperDraft(user_id=principal.user_id, questions=body.questions)
        db.add(row)
    else:
        row.questions = body.questions
    db.commit()
    return {"code": 0, "message": "saved", "data": {"questions": body.questions}}
