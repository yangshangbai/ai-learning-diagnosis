"""Question source management routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from database import get_db
from models.question import QuestionSource, SourceOperation, Question
from schemas.question import SourcePolicyUpdate
from middleware.auth_middleware import get_current_user, require_research_admin

router = APIRouter()


@router.get("/status")
async def get_source_status(
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get question source configuration and status."""
    result = await db.execute(select(QuestionSource))
    sources = result.scalars().all()

    items = []
    for s in sources:
        items.append({
            "id": s.id,
            "name": s.name,
            "status": s.status,
            "priority": s.priority,
            "schedule": s.schedule,
            "min_pool": s.min_pool,
            "last_sync": s.last_sync or "",
            "mapping_coverage": s.mapping_coverage,
            "quality_pass_rate": s.quality_pass_rate,
            "on_demand": s.on_demand,
            "scheduled_sync": s.scheduled_sync,
            "fallback": s.fallback,
        })

    return {"items": items, "total": len(items)}


@router.put("/policy")
async def update_source_policy(
    body: SourcePolicyUpdate,
    db=Depends(get_db),
    _current_user=Depends(require_research_admin),
):
    """Update question source policy configuration."""
    result = await db.execute(select(QuestionSource).limit(1))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="题源配置不存在")

    if body.priority is not None:
        source.priority = body.priority
    if body.schedule is not None:
        source.schedule = body.schedule
    if body.min_pool is not None:
        source.min_pool = body.min_pool
    if body.on_demand is not None:
        source.on_demand = body.on_demand
    if body.scheduled_sync is not None:
        source.scheduled_sync = body.scheduled_sync
    if body.fallback is not None:
        source.fallback = body.fallback

    await db.flush()
    return {"id": source.id, "name": source.name, "message": "策略更新成功"}


@router.post("/sync")
async def trigger_sync(
    db=Depends(get_db),
    _current_user=Depends(require_research_admin),
):
    """Trigger a mock sync operation."""
    result = await db.execute(select(QuestionSource).limit(1))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="题源配置不存在")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    source.last_sync = now_str

    op = SourceOperation(
        source_id=source.id,
        time=now_str,
        type="手动同步",
        detail=f"管理员手动触发同步，完成全学科检查",
        status="完成",
    )
    db.add(op)
    await db.flush()

    return {
        "source_id": source.id,
        "last_sync": now_str,
        "operation_id": op.id,
        "message": "同步完成",
    }


@router.get("/operations")
async def list_source_operations(
    page: int = 1,
    page_size: int = 20,
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List source operation history."""
    from sqlalchemy import func as sql_func

    total_result = await db.execute(
        select(sql_func.count()).select_from(SourceOperation)
    )
    total = total_result.scalar()

    result = await db.execute(
        select(SourceOperation)
        .order_by(SourceOperation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    ops = result.scalars().all()

    items = []
    for op in ops:
        items.append({
            "id": op.id,
            "source_id": op.source_id,
            "time": op.time,
            "type": op.type,
            "detail": op.detail,
            "status": op.status,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


# ── Question Source Candidates ─────────────────────────────────────────────


@router.get("/candidates")
async def list_candidates(
    page: int = 1,
    page_size: int = 20,
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List external question candidates (questions with sync_status='待处理')."""
    from sqlalchemy import func as sql_func

    base_filter = Question.sync_status == "待处理"

    total_result = await db.execute(
        select(sql_func.count()).select_from(Question).where(base_filter)
    )
    total = total_result.scalar()

    result = await db.execute(
        select(Question)
        .where(base_filter)
        .order_by(Question.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    questions = result.scalars().all()

    items = []
    for q in questions:
        items.append({
            "id": q.id,
            "title": q.title,
            "type": q.type,
            "subject": q.subject,
            "grade": q.grade,
            "difficulty": q.difficulty,
            "kp_name": q.kp_name,
            "source": q.source,
            "external_id": q.external_id,
            "sync_status": q.sync_status,
            "usage_count": q.usage_count,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


@router.post("/candidates/{question_id}/accept")
async def accept_candidate(
    question_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_research_admin),
):
    """Accept a question candidate: set sync_status to '已同步' and increment usage_count."""
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    question.sync_status = "已同步"
    question.usage_count = (question.usage_count or 0) + 1
    await db.flush()

    return {"id": question.id, "sync_status": question.sync_status, "message": "已接受候选题目"}


@router.post("/candidates/{question_id}/reject")
async def reject_candidate(
    question_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_research_admin),
):
    """Reject a question candidate: mark sync_status as '已忽略'."""
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    question.sync_status = "已忽略"
    await db.flush()

    return {"id": question.id, "sync_status": question.sync_status, "message": "已忽略候选题目"}
