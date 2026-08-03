"""Question CRUD routes with filtering."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func

from database import get_db
from models.question import Question
from schemas.question import QuestionCreate, QuestionUpdate
from middleware.auth_middleware import get_current_user, require_teacher

router = APIRouter()


@router.get("")
async def list_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: str = Query(None),
    subject: str = Query(None),
    grade: str = Query(None),
    kp_id: int = Query(None),
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List questions with optional filters."""
    query = select(Question)
    count_query = select(func.count()).select_from(Question)

    if source:
        query = query.where(Question.source == source)
        count_query = count_query.where(Question.source == source)
    if subject:
        query = query.where(Question.subject == subject)
        count_query = count_query.where(Question.subject == subject)
    if grade:
        query = query.where(Question.grade == grade)
        count_query = count_query.where(Question.grade == grade)
    if kp_id:
        query = query.where(Question.kp_id == kp_id)
        count_query = count_query.where(Question.kp_id == kp_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )
    questions = result.scalars().all()

    items = []
    for q in questions:
        items.append({
            "id": q.id,
            "title": q.title,
            "type": q.type or "",
            "subject": q.subject or "",
            "grade": q.grade or "",
            "difficulty": q.difficulty or 2,
            "kp_name": q.kp_name or "",
            "kp_id": q.kp_id,
            "source": q.source or "本地题库",
            "external_id": q.external_id or "",
            "sync_status": q.sync_status or "",
            "usage_count": q.usage_count or 0,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


@router.get("/{question_id}")
async def get_question(
    question_id: int,
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get a single question."""
    result = await db.execute(select(Question).where(Question.id == question_id))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    return {
        "id": q.id,
        "title": q.title,
        "type": q.type or "",
        "subject": q.subject or "",
        "grade": q.grade or "",
        "difficulty": q.difficulty or 2,
        "kp_name": q.kp_name or "",
        "kp_id": q.kp_id,
        "source": q.source or "本地题库",
        "external_id": q.external_id or "",
        "sync_status": q.sync_status or "",
        "usage_count": q.usage_count or 0,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }


@router.post("")
async def create_question(
    body: QuestionCreate,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Create a new question."""
    question = Question(
        title=body.title,
        type=body.type,
        subject=body.subject,
        grade=body.grade,
        difficulty=body.difficulty,
        kp_id=body.kp_id,
        kp_name=body.kp_name,
        source=body.source,
        external_id=body.external_id,
    )
    db.add(question)
    await db.flush()
    return {"id": question.id, "title": question.title, "message": "创建成功"}


@router.put("/{question_id}")
async def update_question(
    question_id: int,
    body: QuestionUpdate,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Update a question."""
    result = await db.execute(select(Question).where(Question.id == question_id))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    if body.title is not None:
        q.title = body.title
    if body.type is not None:
        q.type = body.type
    if body.subject is not None:
        q.subject = body.subject
    if body.grade is not None:
        q.grade = body.grade
    if body.difficulty is not None:
        q.difficulty = body.difficulty
    if body.kp_id is not None:
        q.kp_id = body.kp_id
    if body.kp_name is not None:
        q.kp_name = body.kp_name
    if body.source is not None:
        q.source = body.source
    if body.external_id is not None:
        q.external_id = body.external_id
    if body.sync_status is not None:
        q.sync_status = body.sync_status
    if body.usage_count is not None:
        q.usage_count = body.usage_count

    await db.flush()
    return {"id": q.id, "title": q.title, "message": "更新成功"}


@router.delete("/{question_id}")
async def delete_question(
    question_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_teacher),
):
    """Delete a question."""
    result = await db.execute(select(Question).where(Question.id == question_id))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    await db.delete(q)
    await db.flush()
    return {"message": "删除成功"}
