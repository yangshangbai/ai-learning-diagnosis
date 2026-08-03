"""Diagnosis (QuestionResult) routes: CRUD, batch confirm, dashboard."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update

from database import get_db
from models.diagnosis import QuestionResult
from models.task import Task
from models.student import Student
from schemas.diagnosis import DiagnosisUpdate, BatchConfirmRequest
from middleware.auth_middleware import get_current_user, require_teacher

router = APIRouter()


@router.get("")
async def list_diagnoses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    task_id: int = Query(None),
    student_id: int = Query(None),
    verdict: str = Query(None),
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List diagnoses with optional task/student/verdict filters."""
    query = select(QuestionResult)
    count_query = select(func.count()).select_from(QuestionResult)

    if task_id:
        query = query.where(QuestionResult.task_id == task_id)
        count_query = count_query.where(QuestionResult.task_id == task_id)
    if student_id:
        query = query.where(QuestionResult.student_id == student_id)
        count_query = count_query.where(QuestionResult.student_id == student_id)
    if verdict:
        query = query.where(QuestionResult.verdict == verdict)
        count_query = count_query.where(QuestionResult.verdict == verdict)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    result = await db.execute(
        query.order_by(QuestionResult.question_number)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    diagnoses = result.scalars().all()

    items = []
    for d in diagnoses:
        # Get task name
        task_name = ""
        if d.task_id:
            t_result = await db.execute(select(Task).where(Task.id == d.task_id))
            t = t_result.scalar_one_or_none()
            task_name = t.name if t else ""

        # Get student name
        student_name = ""
        if d.student_id:
            s_result = await db.execute(select(Student).where(Student.id == d.student_id))
            s = s_result.scalar_one_or_none()
            student_name = s.name if s else ""

        items.append({
            "id": d.id,
            "task_id": d.task_id,
            "student_id": d.student_id,
            "question_number": d.question_number,
            "verdict": d.verdict or "",
            "ocr_text": d.ocr_text or "",
            "wrong_step": d.wrong_step or "",
            "primary_kp_id": d.primary_kp_id,
            "related_kps": json.loads(d.related_kps) if d.related_kps else [],
            "kp_name": d.kp_name or "",
            "error_cause": d.error_cause or "",
            "skill_cause": d.skill_cause or "",
            "ability_dimension": d.ability_dimension or "",
            "ai_explain": d.ai_explain or "",
            "ai_confidence": d.ai_confidence or 0.0,
            "ai_raw_json": d.ai_raw_json or "{}",
            "is_typical": d.is_typical or False,
            "teacher_verdict": d.teacher_verdict or "",
            "teacher_note": d.teacher_note or "",
            "teacher_modified": d.teacher_modified or False,
            "confirmed_at": d.confirmed_at.isoformat() if d.confirmed_at else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "task_name": task_name,
            "student_name": student_name,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


# ── Static routes MUST be before parameterized routes ──────────────────

@router.post("/batch-confirm")
async def batch_confirm(
    body: BatchConfirmRequest,
    db=Depends(get_db),
    current_user=Depends(require_teacher),
):
    """Batch confirm diagnoses by IDs or by minimum confidence threshold."""
    count = 0

    if body.diagnosis_ids:
        for did in body.diagnosis_ids:
            result = await db.execute(
                select(QuestionResult).where(QuestionResult.id == did)
            )
            d = result.scalar_one_or_none()
            if d:
                d.teacher_verdict = d.verdict
                d.teacher_modified = True
                d.confirmed_at = datetime.utcnow()
                count += 1
    else:
        all_result = await db.execute(
            select(QuestionResult).where(
                QuestionResult.ai_confidence >= body.min_confidence,
                QuestionResult.teacher_verdict == "",
            )
        )
        diagnoses = all_result.scalars().all()
        for d in diagnoses:
            d.teacher_verdict = d.verdict
            d.teacher_modified = True
            d.confirmed_at = datetime.utcnow()
            count += 1

    await db.flush()
    return {"confirmed_count": count, "message": f"批量确认了{count}条诊断"}


def _empty_board_response():
    return {
        "items": [], "total": 0,
        "stats": {"correct": 0, "incorrect": 0, "partially_correct": 0, "uncertain": 0},
    }


@router.get("/board")
async def diagnosis_board(
    task_id: int = Query(None),
    student_id: int = Query(None),
    grade: str = Query(None),
    subject: str = Query(None),
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get diagnosis dashboard/board data for heatmap view.
    Supports filtering by task, student, grade, or subject."""
    query = select(QuestionResult)

    if task_id:
        query = query.where(QuestionResult.task_id == task_id)
    if student_id:
        query = query.where(QuestionResult.student_id == student_id)

    # Filter by grade: find tasks that match the grade
    if grade:
        grade_tasks = await db.execute(
            select(Task.id).where(Task.grade == grade)
        )
        task_ids = [t[0] for t in grade_tasks.all()]
        if task_ids:
            query = query.where(QuestionResult.task_id.in_(task_ids))
        else:
            # No tasks for this grade → return empty
            return _empty_board_response()

    # Filter by subject
    if subject:
        subject_tasks = await db.execute(
            select(Task.id).where(Task.subject == subject)
        )
        task_ids = [t[0] for t in subject_tasks.all()]
        if task_ids:
            query = query.where(QuestionResult.task_id.in_(task_ids))
        else:
            return _empty_board_response()

    # Also apply grade+subject combined if both present
    if grade and subject:
        combined_tasks = await db.execute(
            select(Task.id).where(Task.grade == grade, Task.subject == subject)
        )
        task_ids = [t[0] for t in combined_tasks.all()]
        if task_ids:
            query = select(QuestionResult).where(QuestionResult.task_id.in_(task_ids))
        else:
            return _empty_board_response()

    result = await db.execute(query.order_by(QuestionResult.question_number))
    diagnoses = result.scalars().all()

    items = []
    for d in diagnoses:
        student_name = ""
        if d.student_id:
            s_result = await db.execute(select(Student).where(Student.id == d.student_id))
            s = s_result.scalar_one_or_none()
            student_name = s.name if s else ""

        items.append({
            "id": d.id,
            "question_number": d.question_number,
            "student_id": d.student_id,
            "student_name": student_name,
            "verdict": d.verdict or "",
            "kp_name": d.kp_name or "",
            "error_cause": d.error_cause or "",
            "skill_cause": d.skill_cause or "",
            "ability_dimension": d.ability_dimension or "",
            "ai_confidence": d.ai_confidence or 0.0,
            "is_typical": d.is_typical or False,
            "teacher_verdict": d.teacher_verdict or "",
            "teacher_modified": d.teacher_modified or False,
        })

    total = len(items)
    correct = sum(1 for i in items if i["verdict"] == "correct")
    incorrect = sum(1 for i in items if i["verdict"] == "incorrect")
    partial = sum(1 for i in items if i["verdict"] == "partially_correct")
    uncertain = sum(1 for i in items if i["verdict"] == "uncertain")

    return {
        "items": items,
        "total": total,
        "stats": {
            "correct": correct,
            "incorrect": incorrect,
            "partially_correct": partial,
            "uncertain": uncertain,
        },
    }


# ── Parameterized routes ──────────────────────────────────────────────

@router.get("/{diagnosis_id}")
async def get_diagnosis(
    diagnosis_id: int,
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get a single diagnosis result."""
    result = await db.execute(
        select(QuestionResult).where(QuestionResult.id == diagnosis_id)
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="诊断结果不存在")

    task_name = ""
    if d.task_id:
        t_result = await db.execute(select(Task).where(Task.id == d.task_id))
        t = t_result.scalar_one_or_none()
        task_name = t.name if t else ""

    student_name = ""
    if d.student_id:
        s_result = await db.execute(select(Student).where(Student.id == d.student_id))
        s = s_result.scalar_one_or_none()
        student_name = s.name if s else ""

    return {
        "id": d.id,
        "task_id": d.task_id,
        "student_id": d.student_id,
        "question_number": d.question_number,
        "verdict": d.verdict or "",
        "ocr_text": d.ocr_text or "",
        "wrong_step": d.wrong_step or "",
        "primary_kp_id": d.primary_kp_id,
        "related_kps": json.loads(d.related_kps) if d.related_kps else [],
        "kp_name": d.kp_name or "",
        "error_cause": d.error_cause or "",
        "skill_cause": d.skill_cause or "",
        "ability_dimension": d.ability_dimension or "",
        "ai_explain": d.ai_explain or "",
        "ai_confidence": d.ai_confidence or 0.0,
        "ai_raw_json": d.ai_raw_json or "{}",
        "is_typical": d.is_typical or False,
        "teacher_verdict": d.teacher_verdict or "",
        "teacher_note": d.teacher_note or "",
        "teacher_modified": d.teacher_modified or False,
        "confirmed_at": d.confirmed_at.isoformat() if d.confirmed_at else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "task_name": task_name,
        "student_name": student_name,
    }


@router.put("/{diagnosis_id}")
async def update_diagnosis(
    diagnosis_id: int,
    body: DiagnosisUpdate,
    db=Depends(get_db),
    current_user=Depends(require_teacher),
):
    """Teacher confirms or updates a diagnosis result."""
    result = await db.execute(
        select(QuestionResult).where(QuestionResult.id == diagnosis_id)
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="诊断结果不存在")

    if body.teacher_verdict is not None:
        d.teacher_verdict = body.teacher_verdict
        d.teacher_modified = True
    if body.teacher_note is not None:
        d.teacher_note = body.teacher_note
        d.teacher_modified = True
    if body.is_typical is not None:
        d.is_typical = body.is_typical
    if body.verdict is not None:
        d.verdict = body.verdict
    if body.kp_name is not None:
        d.kp_name = body.kp_name
    if body.error_cause is not None:
        d.error_cause = body.error_cause
    if body.skill_cause is not None:
        d.skill_cause = body.skill_cause
    if body.ability_dimension is not None:
        d.ability_dimension = body.ability_dimension
    if body.ai_explain is not None:
        d.ai_explain = body.ai_explain
    if body.wrong_step is not None:
        d.wrong_step = body.wrong_step
    if body.ocr_text is not None:
        d.ocr_text = body.ocr_text

    if d.teacher_verdict:
        d.confirmed_at = datetime.utcnow()

    await db.flush()

    if d.task_id:
        count_result = await db.execute(
            select(func.count())
            .select_from(QuestionResult)
            .where(
                QuestionResult.task_id == d.task_id,
                QuestionResult.teacher_verdict != "",
            )
        )
        confirmed = count_result.scalar()

        t_result = await db.execute(select(Task).where(Task.id == d.task_id))
        task = t_result.scalar_one_or_none()
        if task:
            task.confirmed_count = confirmed

    await db.flush()
    return {"id": d.id, "teacher_verdict": d.teacher_verdict, "message": "诊断已更新"}
