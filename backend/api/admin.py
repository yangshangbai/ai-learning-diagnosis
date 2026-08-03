"""Admin routes: dashboard statistics and system management."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func

from database import get_db
from models.user import User
from models.student import Student
from models.task import Task
from models.diagnosis import QuestionResult
from models.audit import AuditLog
from schemas.dashboard import DashboardStats
from middleware.auth_middleware import get_current_user, require_admin, require_super

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db=Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Get aggregate dashboard statistics."""
    # Count students
    student_count_result = await db.execute(
        select(func.count()).select_from(Student)
    )
    total_students = student_count_result.scalar()

    # Count teachers
    teacher_count_result = await db.execute(
        select(func.count()).select_from(User).where(User.role == "teacher")
    )
    total_teachers = teacher_count_result.scalar()

    # Count tasks
    task_count_result = await db.execute(
        select(func.count()).select_from(Task)
    )
    total_tasks = task_count_result.scalar()

    # Count pending review tasks
    pending_result = await db.execute(
        select(func.count()).select_from(Task).where(Task.status.in_(["pending_review", "partial_confirmed"]))
    )
    pending_review = pending_result.scalar()

    # AI success rate (diagnoses with confidence >= 0.7)
    total_diag_result = await db.execute(
        select(func.count()).select_from(QuestionResult)
    )
    total_diagnoses = total_diag_result.scalar() or 1

    high_conf_result = await db.execute(
        select(func.count()).select_from(QuestionResult).where(
            QuestionResult.ai_confidence >= 0.7
        )
    )
    high_conf = high_conf_result.scalar() or 0
    ai_success_rate = round(high_conf / total_diagnoses * 100, 1)

    # Average mastery
    avg_mastery_result = await db.execute(
        select(func.avg(Student.mastery)).select_from(Student)
    )
    avg_mastery = avg_mastery_result.scalar() or 0.0
    avg_mastery = round(avg_mastery, 1)

    # Completion rate (tasks completed / total tasks)
    completed_result = await db.execute(
        select(func.count()).select_from(Task).where(Task.status == "completed")
    )
    completed = completed_result.scalar() or 0
    completion_rate = round(completed / max(total_tasks, 1) * 100, 1)

    # Grade distribution
    from models.class_ import Class, Grade
    grades_result = await db.execute(select(Grade).order_by(Grade.sort_order))
    grades = grades_result.scalars().all()
    grade_distribution = []
    for g in grades:
        # Count students in this grade
        cls_sub = select(Class.id).where(Class.grade_id == g.id)
        count_result = await db.execute(
            select(func.count()).select_from(Student).where(Student.class_id.in_(cls_sub))
        )
        cnt = count_result.scalar() or 0

        # Avg mastery in this grade
        avg_result = await db.execute(
            select(func.avg(Student.mastery)).select_from(Student).where(Student.class_id.in_(cls_sub))
        )
        avg_m = avg_result.scalar() or 0.0

        grade_distribution.append({
            "grade": g.name,
            "count": cnt,
            "mastery": round(avg_m, 1),
        })

    # Top weaknesses - simplified: get KPs with diagnoses
    top_weaknesses = []
    try:
        kp_results = await db.execute(
            select(
                QuestionResult.kp_name,
                func.count().label("total"),
            )
            .where(QuestionResult.kp_name != "")
            .group_by(QuestionResult.kp_name)
            .order_by(func.count().desc())
            .limit(10)
        )
        for row in kp_results:
            kp_name, total_q = row
            # Count incorrect for this KP
            incorrect_res = await db.execute(
                select(func.count())
                .where(QuestionResult.kp_name == kp_name, QuestionResult.verdict == "incorrect")
            )
            incorrect_q = incorrect_res.scalar() or 0
            correct_rate = round((1 - incorrect_q / max(total_q, 1)) * 100, 1)
            top_weaknesses.append({
                "kp_name": kp_name,
                "correct_rate": correct_rate,
                "student_count": total_q,
            })
    except Exception:
        top_weaknesses = []

    return DashboardStats(
        total_students=total_students,
        total_teachers=total_teachers,
        total_tasks=total_tasks,
        pending_review=pending_review,
        ai_success_rate=ai_success_rate,
        avg_mastery=avg_mastery,
        completion_rate=completion_rate,
        grade_distribution=grade_distribution,
        top_weaknesses=top_weaknesses,
    )


# ── Remote Help ────────────────────────────────────────────────────────────

from pydantic import BaseModel


class RemoteHelpRequest(BaseModel):
    teacher_id: int
    action: str
    detail: str


@router.post("/remote-help")
async def create_remote_help(
    body: RemoteHelpRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Log a remote help action as an audit entry."""
    # Verify teacher exists
    teacher_result = await db.execute(select(User).where(User.id == body.teacher_id))
    teacher = teacher_result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    audit = AuditLog(
        operator_name=current_user.name,
        operator_id=current_user.id,
        action=f"远程协助: {body.action}",
        target=f"教师 {teacher.name} (id={teacher.id}): {body.detail}",
        ip_address="",
        is_ai_call=False,
    )
    db.add(audit)
    await db.flush()

    return {"message": "远程协助记录成功", "audit_id": audit.id}


@router.get("/remote-help/history")
async def list_remote_help_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List recent remote help audit entries (action contains '远程协助')."""
    from sqlalchemy import func as sql_func

    base_filter = AuditLog.action.contains("远程协助")

    total_result = await db.execute(
        select(sql_func.count()).select_from(AuditLog).where(base_filter)
    )
    total = total_result.scalar()

    result = await db.execute(
        select(AuditLog)
        .where(base_filter)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()

    items = []
    for log in logs:
        items.append({
            "id": log.id,
            "operator_name": log.operator_name,
            "operator_id": log.operator_id,
            "action": log.action,
            "target": log.target,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


# ── AI Configuration ──────────────────────────────────────────────────────

class AIConfigItem(BaseModel):
    provider: str = ""
    model_name: str = ""
    api_key: str = ""
    base_url: str = ""
    description: str = ""
    is_active: bool = False
    settings_json: str = "{}"


class AIConfigUpdate(BaseModel):
    """Bulk update all AI configs at once."""
    configs: list[AIConfigItem] = []


@router.get("/ai-config")
async def get_ai_config(
    db=Depends(get_db),
    _current_user=Depends(require_super),
):
    """Get all AI provider configurations (super admin only)."""
    from models.ai_config import AIConfig

    result = await db.execute(select(AIConfig).order_by(AIConfig.id))
    configs = result.scalars().all()

    providers = [
        {"provider": "mock", "model_name": "Mock AI", "description": "本地模拟AI（开发测试用）"},
        {"provider": "zhipu", "model_name": "glm-4v", "description": "智谱GLM-4V（国产多模态·图片识别）"},
        {"provider": "deepseek", "model_name": "deepseek-chat", "description": "DeepSeek（文本分析·数据诊断）"},
        {"provider": "openai", "model_name": "gpt-4o", "description": "OpenAI GPT-4o（视觉识别+分析）"},
        {"provider": "claude", "model_name": "claude-3-opus", "description": "Anthropic Claude 3（教育领域优化）"},
        {"provider": "paddle", "model_name": "PaddleOCR", "description": "百度PaddleOCR + 文心一言"},
        {"provider": "qwen", "model_name": "qwen-vl-max", "description": "通义千问VL（阿里云）"},
    ]

    # Merge saved configs with provider defaults
    saved_map = {c.provider: c for c in configs}
    items = []
    for p in providers:
        saved = saved_map.get(p["provider"])
        items.append({
            "id": saved.id if saved else None,
            "provider": p["provider"],
            "model_name": saved.model_name if saved else p["model_name"],
            "api_key": saved.api_key if saved else "",
            "base_url": saved.base_url if saved else "",
            "description": saved.description if saved else p["description"],
            "is_active": saved.is_active if saved else (p["provider"] == "mock"),
            "settings_json": saved.settings_json if saved else "{}",
            "updated_at": saved.updated_at.isoformat() if saved and saved.updated_at else None,
        })

    return {"items": items, "total": len(items)}


@router.put("/ai-config")
async def update_ai_config(
    body: AIConfigUpdate,
    db=Depends(get_db),
    current_user=Depends(require_super),
):
    """Save AI provider configurations (super admin only). Accepts full list."""
    from models.ai_config import AIConfig

    updated_count = 0
    for item in body.configs:
        # Find existing or create new
        result = await db.execute(
            select(AIConfig).where(AIConfig.provider == item.provider)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.model_name = item.model_name
            existing.api_key = item.api_key
            existing.base_url = item.base_url
            existing.description = item.description
            existing.is_active = item.is_active
            existing.settings_json = item.settings_json
            existing.updated_at = datetime.utcnow()
        else:
            config = AIConfig(
                provider=item.provider,
                model_name=item.model_name,
                api_key=item.api_key,
                base_url=item.base_url,
                description=item.description,
                is_active=item.is_active,
                settings_json=item.settings_json,
            )
            db.add(config)
        updated_count += 1

    await db.flush()

    # Create audit log
    audit = AuditLog(
        operator_name=current_user.name,
        operator_id=current_user.id,
        action="修改AI配置",
        target=f"更新了 {updated_count} 个AI服务商配置",
        ip_address="",
        is_ai_call=False,
    )
    db.add(audit)
    await db.flush()

    return {"message": f"已保存 {updated_count} 个AI配置", "count": updated_count}
