"""Feedback API — 修改意见和BUG提交."""

import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from database import get_db
from middleware.auth_middleware import get_current_user
from models.feedback import Feedback
from models.user import User
from schemas.feedback import (
    FeedbackCreate, FeedbackUpdate, FeedbackOut, FeedbackListOut,
)

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "feedback")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _can_edit(fb: Feedback, user: User) -> bool:
    """本人可编辑自己已提交的；管理员/超管可删任何。"""
    is_owner = fb.user_id == user.id
    is_admin = user.role in ("admin", "super")
    return (is_owner or is_admin) and fb.status == "已提交"


def _to_out(fb: Feedback) -> dict:
    return {
        "id": fb.id,
        "user_id": fb.user_id,
        "username": fb.username,
        "title": fb.title,
        "content": fb.content,
        "images": fb.images or [],
        "status": fb.status,
        "submitted_at": fb.submitted_at,
        "accepted_at": fb.accepted_at,
        "completed_at": fb.completed_at,
        "created_at": fb.created_at,
    }


# ---------------------------------------------------------------------------
# 图片上传
# ---------------------------------------------------------------------------
@router.post("/upload")
async def upload_feedback_image(file: UploadFile = File(...)):
    """上传反馈图片，返回可访问的URL路径。"""
    ext = os.path.splitext(file.filename or ".png")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件类型: {ext}")

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    return {
        "filename": filename,
        "url": f"/api/feedback/preview/{filename}",
        "message": "上传成功",
    }


@router.get("/preview/{filename}")
async def preview_feedback_image(filename: str):
    """预览反馈图片（免认证，img标签用）。"""
    from fastapi.responses import FileResponse
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "图片不存在")
    return FileResponse(filepath)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
@router.get("")
async def list_feedbacks(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取反馈列表。"""
    q = select(Feedback)
    count_q = select(func.count(Feedback.id))

    if status:
        q = q.where(Feedback.status == status)
        count_q = count_q.where(Feedback.status == status)

    if search:
        like = f"%{search}%"
        q = q.where(or_(Feedback.title.ilike(like), Feedback.content.ilike(like)))
        count_q = count_q.where(or_(Feedback.title.ilike(like), Feedback.content.ilike(like)))

    # Count
    total_res = await db.execute(count_q)
    total = total_res.scalar() or 0

    # Page
    q = q.order_by(Feedback.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    return FeedbackListOut(
        items=[FeedbackOut(**_to_out(r)) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{feedback_id}")
async def get_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查看单条反馈."""
    fb = await db.get(Feedback, feedback_id)
    if not fb:
        raise HTTPException(404, "反馈不存在")
    return FeedbackOut(**_to_out(fb))


@router.post("")
async def create_feedback(
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建反馈."""
    fb = Feedback(
        user_id=current_user.id,
        username=current_user.name or current_user.phone,
        title=body.title,
        content=body.content,
        images=body.images or [],
        status="已提交",
        submitted_at=datetime.utcnow(),
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return FeedbackOut(**_to_out(fb))


@router.put("/{feedback_id}")
async def update_feedback(
    feedback_id: int,
    body: FeedbackUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑反馈（仅已提交状态 + 本人/管理员）."""
    fb = await db.get(Feedback, feedback_id)
    if not fb:
        raise HTTPException(404, "反馈不存在")
    if not _can_edit(fb, current_user):
        raise HTTPException(403, "仅可编辑自己已提交状态的反馈")

    if body.title is not None:
        fb.title = body.title
    if body.content is not None:
        fb.content = body.content
    if body.images is not None:
        fb.images = body.images

    await db.commit()
    await db.refresh(fb)
    return FeedbackOut(**_to_out(fb))


@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除反馈（仅已提交状态 + 本人/管理员）."""
    fb = await db.get(Feedback, feedback_id)
    if not fb:
        raise HTTPException(404, "反馈不存在")
    if not _can_edit(fb, current_user):
        raise HTTPException(403, "仅可删除自己已提交状态的反馈")

    await db.delete(fb)
    await db.commit()
    return {"message": "删除成功"}


# ---------------------------------------------------------------------------
# 状态流转 (admin/super)
# ---------------------------------------------------------------------------
@router.put("/{feedback_id}/accept")
async def accept_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """受理反馈."""
    if current_user.role not in ("admin", "super"):
        raise HTTPException(403, "仅管理员可受理")

    fb = await db.get(Feedback, feedback_id)
    if not fb:
        raise HTTPException(404, "反馈不存在")
    if fb.status != "已提交":
        raise HTTPException(400, f"当前状态为「{fb.status}」，不可受理")

    fb.status = "已受理"
    fb.accepted_at = datetime.utcnow()
    await db.commit()
    await db.refresh(fb)
    return FeedbackOut(**_to_out(fb))


@router.put("/{feedback_id}/complete")
async def complete_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """完成反馈."""
    if current_user.role not in ("admin", "super"):
        raise HTTPException(403, "仅管理员可完成")

    fb = await db.get(Feedback, feedback_id)
    if not fb:
        raise HTTPException(404, "反馈不存在")
    if fb.status != "已受理":
        raise HTTPException(400, f"当前状态为「{fb.status}」，需先受理")

    fb.status = "已完成"
    fb.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(fb)
    return FeedbackOut(**_to_out(fb))
