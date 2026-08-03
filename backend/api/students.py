"""Student CRUD routes with filtering."""

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from database import get_db
from models.student import Student, StudentSnapshot
from models.class_ import Class, Grade
from models.audit import AuditLog
from schemas.student import StudentCreate, StudentUpdate, StudentOut
from middleware.auth_middleware import get_current_user, require_teacher

router = APIRouter()


@router.get("")
async def list_students(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    grade: str = Query(None),
    class_id: int = Query(None),
    name: str = Query(None),
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List students with optional filters."""
    query = select(Student)
    count_query = select(func.count()).select_from(Student)

    if grade:
        # Subquery: class_ids in that grade
        grade_sub = select(Class.id).join(Grade).where(Grade.name == grade)
        query = query.where(Student.class_id.in_(grade_sub))
        count_query = count_query.where(Student.class_id.in_(grade_sub))

    if class_id:
        query = query.where(Student.class_id == class_id)
        count_query = count_query.where(Student.class_id == class_id)

    if name:
        query = query.where(Student.name.contains(name))
        count_query = count_query.where(Student.name.contains(name))

    # Count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Fetch
    result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )
    students = result.scalars().all()

    # Build enriched items
    items = []
    for s in students:
        # Get class info
        cls_result = await db.execute(select(Class).where(Class.id == s.class_id))
        cls = cls_result.scalar_one_or_none()
        class_name = cls.name if cls else ""
        grade_name = ""
        if cls:
            grade_result = await db.execute(select(Grade).where(Grade.id == cls.grade_id))
            g = grade_result.scalar_one_or_none()
            grade_name = g.name if g else ""

        items.append({
            "id": s.id,
            "name": s.name,
            "class_id": s.class_id,
            "class_name": class_name,
            "grade": grade_name,
            "mastery": s.mastery,
            "trend": s.trend,
            "weak_points": json.loads(s.weak_points) if s.weak_points else [],
            "avatar_color": s.avatar_color or "",
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


@router.get("/{student_id}")
async def get_student(
    student_id: int,
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get a single student with class and grade info."""
    result = await db.execute(select(Student).where(Student.id == student_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="学生不存在")

    cls_result = await db.execute(select(Class).where(Class.id == s.class_id))
    cls = cls_result.scalar_one_or_none()
    class_name = cls.name if cls else ""
    grade_name = ""
    if cls:
        grade_result = await db.execute(select(Grade).where(Grade.id == cls.grade_id))
        g = grade_result.scalar_one_or_none()
        grade_name = g.name if g else ""

    return {
        "id": s.id,
        "name": s.name,
        "class_id": s.class_id,
        "class_name": class_name,
        "grade": grade_name,
        "mastery": s.mastery,
        "trend": s.trend,
        "weak_points": json.loads(s.weak_points) if s.weak_points else [],
        "avatar_color": s.avatar_color or "",
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.post("")
async def create_student(
    body: StudentCreate,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Create a new student."""
    # Verify class exists
    cls_result = await db.execute(select(Class).where(Class.id == body.class_id))
    if not cls_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="班级不存在")

    student = Student(
        name=body.name,
        class_id=body.class_id,
        mastery=body.mastery,
        trend=body.trend,
        weak_points=json.dumps(body.weak_points, ensure_ascii=False),
        avatar_color=body.avatar_color,
    )
    db.add(student)
    await db.flush()

    return {
        "id": student.id,
        "name": student.name,
        "class_id": student.class_id,
        "mastery": student.mastery,
        "message": "创建成功",
    }


@router.put("/{student_id}")
async def update_student(
    student_id: int,
    body: StudentUpdate,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Update a student."""
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    if body.name is not None:
        student.name = body.name
    if body.class_id is not None:
        student.class_id = body.class_id
    if body.mastery is not None:
        student.mastery = body.mastery
    if body.trend is not None:
        student.trend = body.trend
    if body.weak_points is not None:
        student.weak_points = json.dumps(body.weak_points, ensure_ascii=False)
    if body.avatar_color is not None:
        student.avatar_color = body.avatar_color

    await db.flush()
    return {"id": student.id, "name": student.name, "message": "更新成功"}


@router.delete("/{student_id}")
async def delete_student(
    student_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Delete a student. Prevent deletion if diagnoses, plans, or snapshots exist."""
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # Check for existing diagnoses
    from models.diagnosis import QuestionResult
    diag_count_result = await db.execute(
        select(func.count()).select_from(QuestionResult).where(QuestionResult.student_id == student_id)
    )
    if diag_count_result.scalar() > 0:
        raise HTTPException(status_code=409, detail="该学生存在诊断记录，无法删除。请先删除相关诊断数据")

    # Check for existing exercise plans
    from models.exercise import ExercisePlan
    plan_count_result = await db.execute(
        select(func.count()).select_from(ExercisePlan).where(ExercisePlan.student_id == student_id)
    )
    if plan_count_result.scalar() > 0:
        raise HTTPException(status_code=409, detail="该学生存在练习计划，无法删除。请先删除相关练习计划")

    # Check for existing snapshots
    snap_count_result = await db.execute(
        select(func.count()).select_from(StudentSnapshot).where(StudentSnapshot.student_id == student_id)
    )
    if snap_count_result.scalar() > 0:
        raise HTTPException(status_code=409, detail="该学生存在学习快照，无法删除。请先删除相关快照数据")

    await db.delete(student)
    await db.flush()
    return {"message": "删除成功"}


# ── Student Snapshots ──────────────────────────────────────────────────────

@router.post("/{student_id}/snapshot")
async def create_student_snapshot(
    student_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Generate a student snapshot capturing current mastery, KP data, abilities, error causes."""
    # Verify student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # Gather KP mastery from question results
    from models.diagnosis import QuestionResult
    from sqlalchemy import func as sql_func, case

    kp_rows = await db.execute(
        select(
            QuestionResult.kp_name,
            sql_func.count().label("total"),
            sql_func.sum(
                case((QuestionResult.verdict == "correct", 1), else_=0)
            ).label("correct"),
        )
        .where(QuestionResult.student_id == student_id, QuestionResult.kp_name != "")
        .group_by(QuestionResult.kp_name)
    )
    kp_mastery = {}
    for row in kp_rows:
        kp_name, total_q, correct_q = row
        rate = round((correct_q or 0) / max(total_q, 1) * 100, 1)
        kp_mastery[kp_name] = {"total": total_q, "correct": correct_q or 0, "rate": rate}

    # Gather ability dimension stats
    ability_rows = await db.execute(
        select(
            QuestionResult.ability_dimension,
            sql_func.count().label("cnt"),
        )
        .where(QuestionResult.student_id == student_id, QuestionResult.ability_dimension != "")
        .group_by(QuestionResult.ability_dimension)
    )
    ability_radar = {}
    for row in ability_rows:
        dim, cnt = row
        ability_radar[dim] = cnt

    # Gather error causes
    error_rows = await db.execute(
        select(
            QuestionResult.error_cause,
            sql_func.count().label("cnt"),
        )
        .where(
            QuestionResult.student_id == student_id,
            QuestionResult.error_cause != "",
            QuestionResult.error_cause != None,
        )
        .group_by(QuestionResult.error_cause)
    )
    error_causes = []
    for row in error_rows:
        cause, cnt = row
        error_causes.append({"cause": cause, "count": cnt})

    snapshot = StudentSnapshot(
        student_id=student_id,
        snapshot_date=date.today(),
        kp_mastery_json=json.dumps(kp_mastery, ensure_ascii=False),
        ability_radar_json=json.dumps(ability_radar, ensure_ascii=False),
        error_causes_json=json.dumps(error_causes, ensure_ascii=False),
        trend=student.trend,
    )
    db.add(snapshot)
    await db.flush()

    return {
        "id": snapshot.id,
        "student_id": snapshot.student_id,
        "snapshot_date": snapshot.snapshot_date.isoformat() if snapshot.snapshot_date else None,
        "kp_mastery": kp_mastery,
        "ability_radar": ability_radar,
        "error_causes": error_causes,
        "trend": snapshot.trend,
        "message": "快照生成成功",
    }


@router.get("/{student_id}/snapshots")
async def list_student_snapshots(
    student_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List all snapshots for a student (paginated)."""
    # Verify student exists
    result = await db.execute(select(Student).where(Student.id == student_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="学生不存在")

    from sqlalchemy import func as sql_func

    total_result = await db.execute(
        select(sql_func.count()).select_from(StudentSnapshot).where(
            StudentSnapshot.student_id == student_id
        )
    )
    total = total_result.scalar()

    snap_result = await db.execute(
        select(StudentSnapshot)
        .where(StudentSnapshot.student_id == student_id)
        .order_by(StudentSnapshot.snapshot_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    snapshots = snap_result.scalars().all()

    items = []
    for snap in snapshots:
        items.append({
            "id": snap.id,
            "student_id": snap.student_id,
            "snapshot_date": snap.snapshot_date.isoformat() if snap.snapshot_date else None,
            "kp_mastery": json.loads(snap.kp_mastery_json) if snap.kp_mastery_json else {},
            "ability_radar": json.loads(snap.ability_radar_json) if snap.ability_radar_json else {},
            "error_causes": json.loads(snap.error_causes_json) if snap.error_causes_json else [],
            "trend": snap.trend,
            "created_at": snap.created_at.isoformat() if snap.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


# ── Student Report ─────────────────────────────────────────────────────────

from pydantic import BaseModel
from typing import Optional, List as PyList


class ReportRequest(BaseModel):
    teacher_comment: str
    recommendations: PyList[str] = []
    stage_name: str = ""
    date_range_from: str = ""
    date_range_to: str = ""


@router.put("/{student_id}/report")
async def save_student_report(
    student_id: int,
    body: ReportRequest,
    db=Depends(get_db),
    current_user=Depends(require_teacher),
):
    """Save a teacher report for a student. Stores as JSON in the Student model and logs an audit entry."""
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    report_data = {
        "teacher_comment": body.teacher_comment,
        "recommendations": body.recommendations,
        "stage_name": body.stage_name,
        "date_range": {
            "from": body.date_range_from,
            "to": body.date_range_to,
        },
    }
    student.report_json = json.dumps(report_data, ensure_ascii=False)

    # Create audit log entry
    audit = AuditLog(
        operator_name=current_user.name,
        operator_id=current_user.id,
        action="保存学生报告",
        target=f"学生 {student.name} (id={student.id})",
        ip_address="",
        is_ai_call=False,
    )
    db.add(audit)
    await db.flush()

    return {"message": "报告保存成功", "student_id": student.id, "audit_id": audit.id}


@router.get("/{student_id}/tasks")
async def get_student_tasks(
    student_id: int,
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get tasks that this student has diagnosis records in (i.e., tasks they participated in)."""
    # Find task_ids from QuestionResult where this student has diagnoses
    from models.diagnosis import QuestionResult
    from models.task import Task
    from models.user import User

    task_ids_subq = select(QuestionResult.task_id).where(QuestionResult.student_id == student_id).distinct()
    result = await db.execute(
        select(Task).where(Task.id.in_(task_ids_subq)).order_by(Task.created_at.desc())
    )
    tasks = result.scalars().all()

    items = []
    for t in tasks:
        creator_name = ""
        if t.creator_id:
            u = await db.execute(select(User).where(User.id == t.creator_id))
            creator = u.scalar_one_or_none()
            creator_name = creator.name if creator else ""

        items.append({
            "id": t.id, "name": t.name, "type": t.type or "", "subject": t.subject or "",
            "grade": t.grade or "", "status": t.status,
            "creator_name": creator_name,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    return {"items": items, "total": len(items)}
