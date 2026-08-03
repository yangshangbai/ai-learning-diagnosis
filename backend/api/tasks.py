"""Task CRUD routes with status management and AI trigger."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from database import get_db
from models.task import Task, TaskClass
from models.class_ import Class, Grade
from models.user import User
from schemas.task import TaskCreate, TaskUpdate, StatusUpdate
from middleware.auth_middleware import get_current_user, require_teacher
from services.task_service import can_transition
from services.ai_service import run_ai_diagnosis as do_ai_diagnosis
from services.snapshot_service import take_snapshots_for_task

router = APIRouter()


@router.get("")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    grade: str = Query(None),
    class_id: int = Query(None),
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List tasks with optional filters, including creator_name and class_names."""
    query = select(Task)
    count_query = select(func.count()).select_from(Task)

    if status:
        query = query.where(Task.status == status)
        count_query = count_query.where(Task.status == status)
    if grade:
        query = query.where(Task.grade == grade)
        count_query = count_query.where(Task.grade == grade)
    if class_id:
        # class_ids stored as JSON string like '["c1","c2"]' or '[1,2]'
        # Use LIKE as a simple approach for SQLite
        query = query.where(Task.class_ids.contains(str(class_id)))
        count_query = count_query.where(Task.class_ids.contains(str(class_id)))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    result = await db.execute(
        query.order_by(Task.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    tasks = result.scalars().all()

    items = []
    for t in tasks:
        # Get creator name
        creator_name = ""
        if t.creator_id:
            u_result = await db.execute(select(User).where(User.id == t.creator_id))
            u = u_result.scalar_one_or_none()
            creator_name = u.name if u else ""

        # Parse class_ids and build class_names
        # Convert string IDs to int for PostgreSQL compatibility (seed data may have "c1" format)
        raw_ids = json.loads(t.class_ids) if t.class_ids else []
        class_ids = []
        for cid in raw_ids:
            try:
                class_ids.append(int(cid) if isinstance(cid, str) and cid.startswith('c') else int(cid))
            except (ValueError, TypeError):
                class_ids.append(cid)
        class_names = ""
        if class_ids:
            cls_result = await db.execute(
                select(Class).where(Class.id.in_(class_ids))
            )
            classes = cls_result.scalars().all()
            class_names = "、".join(c.name for c in classes)

        items.append({
            "id": t.id,
            "name": t.name,
            "type": t.type or "",
            "subject": t.subject or "",
            "grade": t.grade or "",
            "difficulty": t.difficulty or "",
            "pages": t.pages or 0,
            "objective": t.objective or "",
            "status": t.status,
            "kps": json.loads(t.kps) if t.kps else [],
            "class_ids": class_ids,
            "class_names": class_names,
            "confirmed_count": t.confirmed_count or 0,
            "total_count": t.total_count or 0,
            "creator_name": creator_name,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


@router.get("/{task_id}")
async def get_task(
    task_id: int,
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get a single task with full details."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")

    creator_name = ""
    if t.creator_id:
        u_result = await db.execute(select(User).where(User.id == t.creator_id))
        u = u_result.scalar_one_or_none()
        creator_name = u.name if u else ""

    # Parse class_ids and build class_names
    # Convert string IDs to int for PostgreSQL compatibility
    raw_ids = json.loads(t.class_ids) if t.class_ids else []
    class_ids = []
    for cid in raw_ids:
        try:
            class_ids.append(int(cid) if isinstance(cid, str) and cid.startswith('c') else int(cid))
        except (ValueError, TypeError):
            class_ids.append(cid)
    class_names = ""
    if class_ids:
        cls_result = await db.execute(select(Class).where(Class.id.in_(class_ids)))
        classes = cls_result.scalars().all()
        class_names = "、".join(c.name for c in classes)

    return {
        "id": t.id,
        "name": t.name,
        "type": t.type or "",
        "subject": t.subject or "",
        "grade": t.grade or "",
        "difficulty": t.difficulty or "",
        "pages": t.pages or 0,
        "objective": t.objective or "",
        "status": t.status,
        "kps": json.loads(t.kps) if t.kps else [],
        "class_ids": class_ids,
        "class_names": class_names,
        "confirmed_count": t.confirmed_count or 0,
        "total_count": t.total_count or 0,
        "creator_name": creator_name,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.post("")
async def create_task(
    body: TaskCreate,
    db=Depends(get_db),
    current_user=Depends(require_teacher),
):
    """Create a new task."""
    task = Task(
        name=body.name,
        type=body.type,
        subject=body.subject,
        grade=body.grade,
        difficulty=body.difficulty,
        pages=body.pages,
        objective=body.objective,
        kps=json.dumps(body.kps, ensure_ascii=False),
        class_ids=json.dumps(body.class_ids, ensure_ascii=False),
        creator_id=current_user.id,
        status="draft",
    )
    db.add(task)
    await db.flush()

    # Create TaskClass links
    for cid in body.class_ids:
        tc = TaskClass(task_id=task.id, class_id=cid)
        db.add(tc)

    await db.flush()
    return {"id": task.id, "name": task.name, "status": task.status, "message": "创建成功"}


@router.put("/{task_id}")
async def update_task(
    task_id: int,
    body: TaskUpdate,
    db=Depends(get_db),
    current_user=Depends(require_teacher),
):
    """Update a task. Only the creator or admin can modify."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # Ownership check: only creator or admin/super can modify
    if current_user.role not in ("admin", "super") and task.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="只能修改自己创建的任务")

    if body.name is not None:
        task.name = body.name
    if body.type is not None:
        task.type = body.type
    if body.subject is not None:
        task.subject = body.subject
    if body.grade is not None:
        task.grade = body.grade
    if body.class_ids is not None:
        task.class_ids = json.dumps(body.class_ids, ensure_ascii=False)
        # Update TaskClass links
        existing = await db.execute(
            select(TaskClass).where(TaskClass.task_id == task_id)
        )
        for tc in existing.scalars().all():
            await db.delete(tc)
        for cid in body.class_ids:
            tc = TaskClass(task_id=task_id, class_id=cid)
            db.add(tc)
    if body.pages is not None:
        task.pages = body.pages
    if body.objective is not None:
        task.objective = body.objective
    if body.kps is not None:
        task.kps = json.dumps(body.kps, ensure_ascii=False)
    if body.difficulty is not None:
        task.difficulty = body.difficulty
    if body.status is not None:
        if not can_transition(task.status, body.status):
            raise HTTPException(
                status_code=400,
                detail=f"不能从 {task.status} 转换到 {body.status}",
            )
        task.status = body.status

    await db.flush()
    return {"id": task.id, "name": task.name, "message": "更新成功"}


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Delete a task and its class links. Prevent deletion if diagnoses exist."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # Check for existing diagnoses
    from models.diagnosis import QuestionResult
    diag_count_result = await db.execute(
        select(func.count()).select_from(QuestionResult).where(QuestionResult.task_id == task_id)
    )
    if diag_count_result.scalar() > 0:
        raise HTTPException(status_code=409, detail="该任务已有诊断结果，无法删除。如需清除请先联系管理员处理诊断数据")

    # Remove TaskClass links
    existing = await db.execute(
        select(TaskClass).where(TaskClass.task_id == task_id)
    )
    for tc in existing.scalars().all():
        await db.delete(tc)

    await db.delete(task)
    await db.flush()
    return {"message": "删除成功"}


@router.post("/{task_id}/status")
async def update_task_status(
    task_id: int,
    body: StatusUpdate,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Update task status with transition validation."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if not can_transition(task.status, body.status):
        raise HTTPException(
            status_code=400,
            detail=f"不能从 {task.status} 转换到 {body.status}",
        )

    task.status = body.status
    await db.flush()
    return {"id": task.id, "status": task.status, "message": "状态更新成功"}


@router.post("/{task_id}/run-ai")
async def run_ai_diagnosis(
    task_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Trigger mock AI diagnosis for a task."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "pending_upload" and task.status != "ai_processing":
        raise HTTPException(
            status_code=400,
            detail="只能对 pending_upload 或 ai_processing 状态的任务运行AI",
        )

    # Update status to ai_processing
    task.status = "ai_processing"
    await db.flush()

    # Get class_ids and find students
    class_ids = json.loads(task.class_ids) if task.class_ids else []
    from models.student import Student
    students_result = await db.execute(
        select(Student).where(Student.class_id.in_(class_ids))
    )
    students = students_result.scalars().all()

    # Run AI diagnosis for each student (uses GLM-4V if configured, mock as fallback)
    all_results = []
    for student in students:
        results = await do_ai_diagnosis(task.id, student.id, db)
        for r in results:
            db.add(r)
        all_results.extend(results)

    # Update task status to pending_review
    task.status = "pending_review"
    task.total_count = len(all_results)
    await db.flush()

    # Take diagnostic snapshots for each student (background, best-effort)
    try:
        snapshot_count = await take_snapshots_for_task(db, task.id)
    except Exception:
        snapshot_count = 0

    return {
        "task_id": task.id,
        "status": task.status,
        "total_results": len(all_results),
        "students_processed": len(students),
        "snapshots_created": snapshot_count,
        "message": "AI诊断完成",
    }
