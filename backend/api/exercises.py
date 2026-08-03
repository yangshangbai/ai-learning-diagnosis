"""Exercise plan CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func

from database import get_db
from models.exercise import ExercisePlan
from models.student import Student
from schemas.exercise import ExerciseCreate, ExerciseUpdate
from middleware.auth_middleware import get_current_user, require_teacher

router = APIRouter()


@router.get("")
async def list_exercises(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    student_id: int = Query(None),
    status: str = Query(None),
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List exercise plans with optional filters."""
    query = select(ExercisePlan)
    count_query = select(func.count()).select_from(ExercisePlan)

    if student_id:
        query = query.where(ExercisePlan.student_id == student_id)
        count_query = count_query.where(ExercisePlan.student_id == student_id)
    if status:
        query = query.where(ExercisePlan.status == status)
        count_query = count_query.where(ExercisePlan.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    result = await db.execute(
        query.order_by(ExercisePlan.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    plans = result.scalars().all()

    items = []
    for p in plans:
        items.append({
            "id": p.id,
            "student_id": p.student_id,
            "student_name": p.student_name or "",
            "target_kp": p.target_kp or "",
            "frequency": p.frequency or "",
            "question_count": p.question_count or 10,
            "difficulty": p.difficulty or "中等",
            "source": p.source or "",
            "source_trace": p.source_trace or "",
            "status": p.status or "进行中",
            "effect": p.effect or "待观察",
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


@router.post("")
async def create_exercise(
    body: ExerciseCreate,
    db=Depends(get_db),
    current_user=Depends(require_teacher),
):
    """Create a new exercise plan."""
    # Get student name
    student_result = await db.execute(
        select(Student).where(Student.id == body.student_id)
    )
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=400, detail="学生不存在")

    plan = ExercisePlan(
        student_id=body.student_id,
        student_name=student.name,
        target_kp=body.target_kp,
        frequency=body.frequency,
        question_count=body.question_count,
        difficulty=body.difficulty,
        source="统一智能题库",
        status="进行中",
        effect="待观察",
    )
    db.add(plan)
    await db.flush()
    return {
        "id": plan.id,
        "student_name": plan.student_name,
        "target_kp": plan.target_kp,
        "message": "创建成功",
    }


@router.put("/{plan_id}")
async def update_exercise(
    plan_id: int,
    body: ExerciseUpdate,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Update an exercise plan."""
    result = await db.execute(
        select(ExercisePlan).where(ExercisePlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="练习方案不存在")

    if body.student_id is not None:
        plan.student_id = body.student_id
        s_result = await db.execute(select(Student).where(Student.id == body.student_id))
        s = s_result.scalar_one_or_none()
        if s:
            plan.student_name = s.name
    if body.target_kp is not None:
        plan.target_kp = body.target_kp
    if body.frequency is not None:
        plan.frequency = body.frequency
    if body.question_count is not None:
        plan.question_count = body.question_count
    if body.difficulty is not None:
        plan.difficulty = body.difficulty
    if body.status is not None:
        plan.status = body.status
    if body.effect is not None:
        plan.effect = body.effect
    if body.source is not None:
        plan.source = body.source
    if body.source_trace is not None:
        plan.source_trace = body.source_trace

    await db.flush()
    return {"id": plan.id, "target_kp": plan.target_kp, "message": "更新成功"}


@router.delete("/{plan_id}")
async def delete_exercise(
    plan_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Delete an exercise plan."""
    result = await db.execute(
        select(ExercisePlan).where(ExercisePlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="练习方案不存在")

    await db.delete(plan)
    await db.flush()
    return {"message": "删除成功"}
