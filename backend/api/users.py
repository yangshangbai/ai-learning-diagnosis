"""Teacher management routes (users with role=teacher)."""

import json

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from database import get_db
from models.user import User
from models.teacher import TeacherClass
from models.class_ import Class
from middleware.auth_middleware import require_admin
from services.auth_service import hash_password

router = APIRouter()


@router.get("")
async def list_teachers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    _current_user=Depends(require_admin),
):
    """List all teacher users with their class assignments."""
    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(User).where(User.role == "teacher")
    )
    total = count_result.scalar()

    # Query teachers
    result = await db.execute(
        select(User)
        .where(User.role == "teacher")
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    teachers = result.scalars().all()

    items = []
    for t in teachers:
        # Get assigned class IDs
        tc_result = await db.execute(
            select(TeacherClass).where(TeacherClass.teacher_id == t.id)
        )
        teacher_classes = tc_result.scalars().all()
        class_ids = [tc.class_id for tc in teacher_classes]

        items.append({
            "id": t.id,
            "name": t.name,
            "phone": t.phone,
            "role": t.role,
            "avatar": t.avatar or "",
            "grades": json.loads(t.grades) if t.grades else [],
            "subjects": json.loads(t.subjects) if t.subjects else [],
            "class_ids": class_ids,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


from schemas.auth import TeacherCreate, TeacherUpdate


@router.post("")
async def create_teacher(
    body: TeacherCreate,
    db=Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Create a new teacher user."""
    # Check phone uniqueness
    existing = await db.execute(
        select(User).where(User.phone == body.phone)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="手机号已存在",
        )

    user = User(
        phone=body.phone,
        name=body.name,
        role=body.role,
        password_hash=hash_password(body.password),
        avatar=body.name[0] if body.name else "",
        grades=json.dumps(body.grades, ensure_ascii=False),
        subjects=json.dumps(body.subjects, ensure_ascii=False),
    )
    db.add(user)
    await db.flush()

    # Assign classes if provided
    for cid in body.class_ids:
        tc = TeacherClass(teacher_id=user.id, class_id=cid)
        db.add(tc)

    await db.flush()
    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "role": user.role,
        "message": "创建成功",
    }


@router.put("/{user_id}")
async def update_teacher(
    user_id: int,
    body: TeacherUpdate,
    db=Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Update a teacher user."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.role == "teacher")
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="教师不存在")

    # Check phone uniqueness if phone is being changed
    if body.phone is not None and body.phone != user.phone:
        existing = await db.execute(
            select(User).where(User.phone == body.phone, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="手机号已被其他用户使用")

    if body.name is not None:
        user.name = body.name
    if body.phone is not None:
        user.phone = body.phone
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    if body.grades is not None:
        user.grades = json.dumps(body.grades, ensure_ascii=False)
    if body.subjects is not None:
        user.subjects = json.dumps(body.subjects, ensure_ascii=False)

    # Update class assignments if provided
    if body.class_ids is not None:
        existing_tcs = await db.execute(
            select(TeacherClass).where(TeacherClass.teacher_id == user.id)
        )
        for tc in existing_tcs.scalars().all():
            await db.delete(tc)
        for cid in body.class_ids:
            tc = TeacherClass(teacher_id=user.id, class_id=cid)
            db.add(tc)

    await db.flush()
    return {"id": user.id, "name": user.name, "message": "更新成功"}


@router.delete("/{user_id}")
async def delete_teacher(
    user_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Delete a teacher user and their class assignments. Prevent deletion if tasks or audit logs exist."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.role == "teacher")
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="教师不存在")

    # Check for tasks created by this user
    from models.task import Task
    task_count_result = await db.execute(
        select(func.count()).select_from(Task).where(Task.creator_id == user_id)
    )
    if task_count_result.scalar() > 0:
        raise HTTPException(status_code=409, detail="该教师有创建的任务记录，无法删除。请先处理相关任务")

    # Check for audit logs
    from models.audit import AuditLog
    audit_count_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.operator_id == user_id)
    )
    if audit_count_result.scalar() > 0:
        raise HTTPException(status_code=409, detail="该教师有操作日志记录，无法删除。可禁用账号代替删除")

    # Remove class assignments
    tcs = await db.execute(
        select(TeacherClass).where(TeacherClass.teacher_id == user_id)
    )
    for tc in tcs.scalars().all():
        await db.delete(tc)

    await db.delete(user)
    await db.flush()
    return {"message": "删除成功"}
