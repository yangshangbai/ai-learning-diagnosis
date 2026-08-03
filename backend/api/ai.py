"""AI suggestion routes — delegates to ai_service (DeepSeek for text, GLM for vision)."""

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc

from database import get_db
from middleware.auth_middleware import get_current_user
from services.ai_service import get_ai_suggestion, ai_assistant_chat
from models.chat_history import ChatHistory

router = APIRouter()


class SuggestRequest(BaseModel):
    prompt: str


@router.post("/suggest")
async def ai_suggest(
    body: SuggestRequest,
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Return an AI-powered suggestion. Uses DeepSeek when configured, falls back to mock."""
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    suggestion = await get_ai_suggestion(db, body.prompt)
    return {"suggestion": suggestion}


@router.post("/assistant")
async def ai_assistant(
    body: SuggestRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    AI Assistant chat — understands system context, can query real database data.
    Auto-saves conversation to chat_history for the current user.
    """
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    # Save user message
    user_msg = ChatHistory(user_id=current_user.id, role="user", content=body.prompt)
    db.add(user_msg)

    # Get AI reply
    reply = await ai_assistant_chat(db, body.prompt)

    # Save assistant message
    asst_msg = ChatHistory(user_id=current_user.id, role="assistant", content=reply)
    db.add(asst_msg)
    await db.flush()

    return {"reply": reply, "id": asst_msg.id}


# ── Chat History ──────────────────────────────────────────

@router.get("/chat-history")
async def get_chat_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get chat history for the current user, newest first."""
    base = select(ChatHistory).where(ChatHistory.user_id == current_user.id)
    count_q = select(func.count()).select_from(ChatHistory).where(ChatHistory.user_id == current_user.id)

    total = (await db.execute(count_q)).scalar()

    result = await db.execute(
        base.order_by(ChatHistory.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.scalars().all()

    items = [{
        "id": r.id,
        "role": r.role,
        "content": r.content,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.delete("/chat-history")
async def clear_chat_history(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Clear all chat history for the current user."""
    result = await db.execute(
        select(ChatHistory).where(ChatHistory.user_id == current_user.id)
    )
    rows = result.scalars().all()
    count = len(rows)
    for r in rows:
        await db.delete(r)
    await db.flush()
    return {"message": f"已清除 {count} 条聊天记录"}
