"""KnowledgePoint tree CRUD routes."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func

from database import get_db
from models.knowledge import KnowledgePoint
from schemas.knowledge import KPCreate, KPUpdate
from middleware.auth_middleware import get_current_user, require_research_admin

router = APIRouter()


def _build_tree(nodes: list[KnowledgePoint], parent_id=None) -> list:
    """Build nested tree structure from a flat list of nodes."""
    children = []
    for node in nodes:
        if node.parent_id == parent_id:
            child_dict = {
                "id": node.id,
                "parent_id": node.parent_id,
                "name": node.name,
                "subject": node.subject or "",
                "grade": node.grade or "",
                "stage": node.stage or "",
                "level": node.level,
                "keywords": json.loads(node.keywords) if node.keywords else [],
                "sort_order": node.sort_order or 0,
                "mastery": node.mastery or 0.0,
                "children": _build_tree(nodes, node.id),
            }
            children.append(child_dict)
    return children


@router.get("")
async def list_knowledge_tree(
    subject: str = Query(None),
    grade: str = Query(None),
    flat: bool = Query(False),
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get the knowledge tree, optionally filtered by subject and/or grade."""
    query = select(KnowledgePoint)

    if subject:
        query = query.where(KnowledgePoint.subject == subject)
    if grade:
        query = query.where(KnowledgePoint.grade == grade)

    result = await db.execute(query.order_by(KnowledgePoint.sort_order))
    nodes = result.scalars().all()

    if flat:
        items = []
        for n in nodes:
            items.append({
                "id": n.id,
                "parent_id": n.parent_id,
                "name": n.name,
                "subject": n.subject or "",
                "grade": n.grade or "",
                "stage": n.stage or "",
                "level": n.level,
                "keywords": json.loads(n.keywords) if n.keywords else [],
                "sort_order": n.sort_order or 0,
                "mastery": n.mastery or 0.0,
            })
        return {"items": items, "total": len(items)}

    tree = _build_tree(list(nodes))
    return {"items": tree, "total": len(tree)}


@router.get("/{node_id}")
async def get_knowledge_node(
    node_id: int,
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get a single knowledge node with its children."""
    result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.id == node_id)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # Get children
    children_result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.parent_id == node_id)
    )
    children = children_result.scalars().all()

    return {
        "id": node.id,
        "parent_id": node.parent_id,
        "name": node.name,
        "subject": node.subject or "",
        "grade": node.grade or "",
        "stage": node.stage or "",
        "level": node.level,
        "keywords": json.loads(node.keywords) if node.keywords else [],
        "sort_order": node.sort_order or 0,
        "mastery": node.mastery or 0.0,
        "children": [
            {
                "id": c.id,
                "parent_id": c.parent_id,
                "name": c.name,
                "subject": c.subject or "",
                "grade": c.grade or "",
                "stage": c.stage or "",
                "level": c.level,
                "keywords": json.loads(c.keywords) if c.keywords else [],
                "sort_order": c.sort_order or 0,
                "mastery": c.mastery or 0.0,
            }
            for c in children
        ],
    }


@router.post("")
async def create_knowledge_node(
    body: KPCreate,
    db=Depends(get_db),
    _current_user=Depends(require_research_admin),
):
    """Add a knowledge point node."""
    if body.parent_id:
        parent_result = await db.execute(
            select(KnowledgePoint).where(KnowledgePoint.id == body.parent_id)
        )
        if not parent_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="父节点不存在")

    kp = KnowledgePoint(
        name=body.name,
        parent_id=body.parent_id,
        subject=body.subject,
        grade=body.grade,
        stage=body.stage,
        level=body.level,
        keywords=json.dumps(body.keywords, ensure_ascii=False),
        sort_order=body.sort_order,
    )
    db.add(kp)
    await db.flush()
    return {"id": kp.id, "name": kp.name, "message": "创建成功"}


@router.put("/{node_id}")
async def update_knowledge_node(
    node_id: int,
    body: KPUpdate,
    db=Depends(get_db),
    _current_user=Depends(require_research_admin),
):
    """Update a knowledge point node."""
    result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.id == node_id)
    )
    kp = result.scalar_one_or_none()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    if body.name is not None:
        kp.name = body.name
    if body.parent_id is not None:
        kp.parent_id = body.parent_id
    if body.subject is not None:
        kp.subject = body.subject
    if body.grade is not None:
        kp.grade = body.grade
    if body.stage is not None:
        kp.stage = body.stage
    if body.keywords is not None:
        kp.keywords = json.dumps(body.keywords, ensure_ascii=False)
    if body.sort_order is not None:
        kp.sort_order = body.sort_order
    if body.mastery is not None:
        kp.mastery = body.mastery

    await db.flush()
    return {"id": kp.id, "name": kp.name, "message": "更新成功"}


@router.delete("/{node_id}")
async def delete_knowledge_node(
    node_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_research_admin),
):
    """Delete a knowledge point node and reparent children to its parent. Prevent if questions reference it."""
    result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.id == node_id)
    )
    kp = result.scalar_one_or_none()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # Check for questions referencing this KP
    from models.question import Question
    q_count_result = await db.execute(
        select(func.count()).select_from(Question).where(Question.kp_id == node_id)
    )
    if q_count_result.scalar() > 0:
        raise HTTPException(status_code=409, detail=f"有 {q_count_result.scalar()} 道题目引用了该知识点，请先移除题目或更改其知识点后再删除")

    # Check for diagnoses referencing this KP
    from models.diagnosis import QuestionResult
    d_count_result = await db.execute(
        select(func.count()).select_from(QuestionResult).where(QuestionResult.primary_kp_id == node_id)
    )
    if d_count_result.scalar() > 0:
        raise HTTPException(status_code=409, detail="有诊断记录引用了该知识点，无法删除")

    # Reparent children to the deleted node's parent
    children_result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.parent_id == node_id)
    )
    children = children_result.scalars().all()
    for child in children:
        child.parent_id = kp.parent_id

    await db.delete(kp)
    await db.flush()
    return {"message": "删除成功"}
