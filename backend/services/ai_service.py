"""
Unified AI Service — routes to different providers based on task type.

┌─────────────┬──────────────────────┬──────────────────────┐
│  Task       │  Provider            │  Model               │
├─────────────┼──────────────────────┼──────────────────────┤
│  图片识别    │  Zhipu (智谱)        │  glm-4v              │
│  诊断分析    │  DeepSeek            │  deepseek-chat       │
│  AI建议      │  DeepSeek            │  deepseek-chat       │
│  Mock兜底    │  ai_mock.py          │  -                   │
└─────────────┴──────────────────────┴──────────────────────┘

API keys are stored in the ai_configs database table and loaded on demand.
"""
import asyncio
import base64
import json
import logging
import os
import random
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_config import AIConfig
from models.diagnosis import QuestionResult

logger = logging.getLogger("ai_service")

# ── Provider defaults ──────────────────────────────────────
PROVIDER_CONFIGS = {
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "vision_model": "glm-4v",
        "text_model": "glm-4-flash",
        "timeout": 120,
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "timeout": 90,
    },
}


# ═══════════════════════════════════════════════════════════
#  Config Loader
# ═══════════════════════════════════════════════════════════

async def _get_config(db: AsyncSession, provider: str) -> Optional[AIConfig]:
    """Load a provider's config from the database."""
    result = await db.execute(
        select(AIConfig).where(AIConfig.provider == provider)
    )
    return result.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════
#  GLM-4V (Zhipu) — Vision for paper grading
# ═══════════════════════════════════════════════════════════

VISION_SYSTEM_PROMPT = """你是一位专业的中小学数学教师AI助手。请仔细查看学生的手写试卷图片，针对每道题进行诊断。

请以JSON格式返回诊断结果，包含以下字段（返回一个JSON对象，包含questions数组）：
{
  "questions": [
    {
      "num": 1,
      "verdict": "correct|incorrect|partially_correct|uncertain",
      "ocrText": "识别出的学生作答内容",
      "wrongStep": "错误步骤描述（正确则为'无'）",
      "kp": "对应知识点名称（如：分数概念、异分母分数加减、分数应用题建模等）",
      "relatedKps": ["关联知识点1", "关联知识点2"],
      "errorCause": "错因分类（概念混淆|计算失误|建模失败|审题偏差|策略不当|知识遗忘|需人工判断，正确则为空字符串）",
      "skillCause": "技能层面原因（如：程序性知识错误|S型-计算细节错误|审题偏差|低置信度-需人工补录，正确则为'无'）",
      "ability": "能力维度（运算能力|概念理解能力|逻辑推理能力|几何直观能力|应用建模能力|审题能力|表达规范能力）",
      "aiExplain": "简短的AI评语（50字以内）",
      "confidence": 0.85,
      "typical": false
    }
  ]
}

注意：
- verdict必须严格判断答案是否正确
- kp必须精确匹配数学知识点
- 如果是典型错误（班级常见错误），typical设为true
- confidence是AI判断的置信度（0-1）
- 只返回JSON，不要其他内容"""


async def _call_zhipu_vision(
    api_key: str,
    base_url: str,
    model: str,
    image_paths: list[str],
    task_info: str = "",
    timeout: int = 120,
) -> dict:
    """Call Zhipu GLM-4V API to grade a student's paper from images."""
    url = f"{base_url}/chat/completions"

    # Build message content: text prompt + images as base64
    content = []
    content.append({
        "type": "text",
        "text": f"请批改以下试卷。任务信息：{task_info}\n{VISION_SYSTEM_PROMPT}"
    })

    for img_path in image_paths:
        if not os.path.exists(img_path):
            continue
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        ext = os.path.splitext(img_path)[1].lower().replace(".", "")
        mime = f"image/{ext}" if ext in ("jpg", "jpeg", "png", "gif", "webp") else "image/jpeg"
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{img_b64}"}
        })

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.3,
        "max_tokens": 3000,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    # Parse response — expect JSON in content
    content_text = data["choices"][0]["message"]["content"]
    # Strip markdown code fences if present
    content_text = content_text.strip()
    if content_text.startswith("```"):
        content_text = content_text.split("\n", 1)[1] if "\n" in content_text else content_text[3:]
        if content_text.endswith("```"):
            content_text = content_text[:-3]
    return json.loads(content_text)


# ═══════════════════════════════════════════════════════════
#  DeepSeek — Text analysis & suggestions
# ═══════════════════════════════════════════════════════════

DIAGNOSIS_ANALYSIS_PROMPT = """你是一位资深教育数据分析师。请根据以下AI诊断原始数据，生成结构化的教学分析报告。

输入数据（JSON格式的逐题诊断结果）：

请分析并返回JSON：
{
  "summary": "整体总结（100字以内）",
  "correct_rate": 0.5,
  "weak_kps": ["薄弱知识点1", "薄弱知识点2"],
  "common_errors": ["共性错因1", "共性错因2"],
  "recommendations": ["教学建议1", "教学建议2"],
  "student_profile": {
    "strengths": ["优势1"],
    "weaknesses": ["劣势1"],
    "suggested_focus": "建议重点关注方向"
  }
}

只返回JSON，不要其他内容。"""


async def _call_deepseek(
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_message: str,
    timeout: int = 90,
    temperature: float = 0.7,
) -> str:
    """Call DeepSeek API for text analysis/suggestions."""
    url = f"{base_url}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": 2000,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════

async def run_ai_diagnosis(
    task_id: int,
    student_id: int,
    db: AsyncSession,
) -> list[QuestionResult]:
    """
    Run AI diagnosis for one student's paper.
    1. Collect uploaded images for this student+task
    2. Call GLM-4V for vision-based grading
    3. Return QuestionResult objects
    4. Fall back to mock if API unavailable
    """
    # Try real AI first
    zhipu_config = await _get_config(db, "zhipu")
    if zhipu_config and zhipu_config.api_key and zhipu_config.is_active:
        try:
            # Collect uploaded images for this student
            from config import settings
            task_dir = os.path.join(settings.UPLOAD_DIR, f"task_{task_id}", f"student_{student_id}")
            image_paths = []
            if os.path.exists(task_dir):
                for fname in sorted(os.listdir(task_dir)):
                    fpath = os.path.join(task_dir, fname)
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp') and os.path.isfile(fpath):
                        image_paths.append(fpath)

            if image_paths:
                cfg = PROVIDER_CONFIGS["zhipu"]
                base_url = zhipu_config.base_url or cfg["base_url"]
                model = zhipu_config.model_name or cfg["vision_model"]

                result = await _call_zhipu_vision(
                    api_key=zhipu_config.api_key,
                    base_url=base_url,
                    model=model,
                    image_paths=image_paths,
                    task_info=f"task_id={task_id}",
                    timeout=cfg["timeout"],
                )

                # Convert vision result to QuestionResult objects
                diagnoses = []
                for q in result.get("questions", []):
                    diagnoses.append(QuestionResult(
                        task_id=task_id,
                        student_id=student_id,
                        question_number=q.get("num", 0),
                        verdict=q.get("verdict", "uncertain"),
                        ocr_text=q.get("ocrText", ""),
                        wrong_step=q.get("wrongStep", ""),
                        kp_name=q.get("kp", ""),
                        related_kps=json.dumps(q.get("relatedKps", []), ensure_ascii=False),
                        error_cause=q.get("errorCause", ""),
                        skill_cause=q.get("skillCause", ""),
                        ability_dimension=q.get("ability", ""),
                        ai_explain=q.get("aiExplain", ""),
                        ai_confidence=float(q.get("confidence", 0.5)),
                        ai_raw_json=json.dumps(q, ensure_ascii=False),
                        is_typical=bool(q.get("typical", False)),
                        created_at=datetime.utcnow(),
                    ))
                logger.info(f"GLM-4V diagnosed {len(diagnoses)} questions for task={task_id} student={student_id}")
                return diagnoses
        except Exception as e:
            logger.warning(f"GLM-4V vision failed for task={task_id} student={student_id}: {e}")

    # Fall back to mock AI
    from services.ai_mock import run_mock_ai_diagnosis
    logger.info(f"Using mock AI for task={task_id} student={student_id}")
    return await run_mock_ai_diagnosis(task_id, student_id, db)


# ═══════════════════════════════════════════════════════════
#  AI Assistant Chat — with system data query capability
# ═══════════════════════════════════════════════════════════

import json as json_module
from services.system_context import SYSTEM_DESCRIPTION, QUERY_TOOLS, execute_query

ASSISTANT_SYSTEM_PROMPT = f"""你是"AI学习诊断系统"的智能助手。你必须严格按照以下规则回答：

{SYSTEM_DESCRIPTION}

## 你的能力
1. **数据查询**：可以查询系统的实时数据。当你需要数据时，在回答中插入以下格式的查询标记：
   [[QUERY:查询名称|参数JSON]]
   系统会自动执行查询并用真实数据替换标记，然后你基于真实数据回答。
   
   可用查询：
   - [[QUERY:get_system_stats|{{}}]] — 系统整体统计
   - [[QUERY:get_grade_distribution|{{}}]] — 各年级分布
   - [[QUERY:get_top_weaknesses|{{"limit":5}}]] — 最薄弱知识点
   - [[QUERY:get_student_count|{{"grade":"五年级"}}]] — 按年级查学生数
   - [[QUERY:get_teacher_list|{{}}]] — 老师列表
   - [[QUERY:get_task_summary|{{}}]] — 任务状态汇总
   - [[QUERY:get_recent_diagnosis_summary|{{}}]] — 诊断汇总

2. **教学建议**：基于系统数据和教学经验给出建议
3. **操作指导**：告诉用户如何使用系统的各项功能
4. **数据解读**：帮助用户理解诊断数据和学习趋势

## 回答规则
- 如果用户问的是数据类问题（人数、统计、排行等），务必使用[[QUERY:...]]标记查询
- 回答简洁专业，控制在300字以内
- 如果问题超出系统范围，礼貌说明
- 不要编造数据，必须基于查询结果回答"""


async def ai_assistant_chat(db: AsyncSession, user_message: str) -> str:
    """
    AI Assistant chat — understands system context and can query real data.
    Uses DeepSeek for text understanding, executes queries against PostgreSQL.
    """
    deepseek_config = await _get_config(db, "deepseek")

    # Build messages with system context
    messages = [
        {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    if deepseek_config and deepseek_config.api_key and deepseek_config.is_active:
        try:
            cfg = PROVIDER_CONFIGS["deepseek"]
            base_url = deepseek_config.base_url or cfg["base_url"]
            model = deepseek_config.model_name or cfg["model"]

            # First call: DeepSeek responds (may contain QUERY markers)
            url = f"{base_url}/chat/completions"
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 800,
            }
            headers = {
                "Authorization": f"Bearer {deepseek_config.api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=cfg["timeout"]) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            ai_text = data["choices"][0]["message"]["content"]

            # Check if AI requested a query — extract and execute queries
            import re
            query_pattern = re.compile(r'\[\[QUERY:(\w+)\|([^]]*)\]\]')
            matches = list(query_pattern.finditer(ai_text))

            if matches:
                # Execute all queries (async, properly awaited)
                query_results = {}
                for match in matches:
                    qname = match.group(1)
                    try:
                        qparams = json_module.loads(match.group(2)) if match.group(2).strip() else {}
                    except json_module.JSONDecodeError:
                        qparams = {}
                    try:
                        result = await execute_query(db, qname, qparams)
                        query_results[match.group(0)] = json_module.dumps(result, ensure_ascii=False, indent=2)
                    except Exception as e:
                        query_results[match.group(0)] = f"[查询失败: {e}]"

                # Replace query markers with actual data
                enriched = ai_text
                for marker, data_str in query_results.items():
                    enriched = enriched.replace(marker, data_str)

                # Second call: ask DeepSeek to format with the real data
                messages.append({"role": "assistant", "content": ai_text})
                messages.append({"role": "user", "content": f"请基于以下查询结果，用自然语言简洁地回答（100字以内）。\n查询结果：\n{enriched}\n\n用户原问题：{user_message}"})

                payload["messages"] = messages
                payload["max_tokens"] = 400
                async with httpx.AsyncClient(timeout=cfg["timeout"]) as client:
                    resp2 = await client.post(url, json=payload, headers=headers)
                    resp2.raise_for_status()
                    data2 = resp2.json()
                return data2["choices"][0]["message"]["content"].strip()

            return ai_text.strip()

        except Exception as e:
            logger.warning(f"AI assistant chat failed: {e}")

    # Fallback: basic keyword-based responses with real data
    return await _fallback_assistant(db, user_message)


async def _fallback_assistant(db: AsyncSession, message: str) -> str:
    """Fallback assistant when DeepSeek is unavailable. Uses keyword matching + real queries."""
    msg = message.lower()

    # Check for data queries
    if any(w in msg for w in ["学生人数", "学生数", "多少学生", "学生总数"]):
        from models.student import Student
        from sqlalchemy import func
        count = (await db.execute(select(func.count()).select_from(Student))).scalar()
        return f"📊 系统中目前共有 **{count}** 名学生。如需按年级或班级筛选，请告诉我具体的年级或班级名称。"

    if any(w in msg for w in ["老师", "教师", "师资"]):
        from models.user import User
        teachers = (await db.execute(
            select(User.name, User.phone).where(User.role == "teacher")
        )).all()
        lines = [f"👨‍🏫 系统共有 **{len(teachers)}** 位老师："]
        for t in teachers:
            lines.append(f"  · {t[0]} ({t[1]})")
        return "\n".join(lines)

    if any(w in msg for w in ["任务", "task"]):
        from models.task import Task
        total = (await db.execute(select(func.count()).select_from(Task))).scalar()
        pending = (await db.execute(
            select(func.count()).select_from(Task).where(Task.status == "pending_review")
        )).scalar()
        return f"📋 系统共有 **{total}** 个任务，其中 **{pending}** 个待确认批改。"

    if any(w in msg for w in ["年级", "班级分布", "掌握度"]):
        from models.class_ import Grade, Class
        from models.student import Student
        grades = (await db.execute(select(Grade).order_by(Grade.sort_order))).scalars().all()
        lines = ["📚 各年级情况："]
        for g in grades:
            cls_sub = select(Class.id).where(Class.grade_id == g.id)
            cnt = (await db.execute(select(func.count()).select_from(Student).where(Student.class_id.in_(cls_sub)))).scalar()
            avg_m = (await db.execute(select(func.avg(Student.mastery)).select_from(Student).where(Student.class_id.in_(cls_sub)))).scalar() or 0
            lines.append(f"  · {g.name}：{cnt}人，平均掌握度 {round(float(avg_m),1)}%")
        return "\n".join(lines)

    # Generic fallback
    return (
        "🤖 我是AI学习诊断系统的智能助手。我可以帮你：\n\n"
        "📊 **查询数据**：学生人数、老师列表、任务状态、年级分布、薄弱知识点等\n"
        "💡 **教学建议**：根据诊断数据给出针对性建议\n"
        "📖 **操作指导**：告诉你如何使用系统功能\n\n"
        "请直接告诉我你想了解什么，例如：\n"
        "· \"查一下学生人数\"\n"
        "· \"五年级有哪些薄弱知识点\"\n"
        "· \"最近任务情况怎么样\"\n"
        "· \"系统有哪些功能模块\""
    )


async def get_ai_suggestion(db: AsyncSession, prompt: str) -> str:
    """
    Get an AI-powered suggestion for teaching/learning.
    Uses DeepSeek for text analysis, falls back to mock.
    """
    deepseek_config = await _get_config(db, "deepseek")
    if deepseek_config and deepseek_config.api_key and deepseek_config.is_active:
        try:
            cfg = PROVIDER_CONFIGS["deepseek"]
            base_url = deepseek_config.base_url or cfg["base_url"]
            model = deepseek_config.model_name or cfg["model"]

            system_prompt = (
                "你是一位资深的中小学教育专家和教学顾问。请根据用户的问题，"
                "提供专业、具体、可操作的教学建议或学习指导。"
                "回答应简洁明了（200字以内），直接给出建议，不需要客套话。"
            )

            result = await _call_deepseek(
                api_key=deepseek_config.api_key,
                base_url=base_url,
                model=model,
                system_prompt=system_prompt,
                user_message=prompt,
                timeout=cfg["timeout"],
                temperature=0.7,
            )
            logger.info(f"DeepSeek suggestion generated for prompt: {prompt[:50]}...")
            return result.strip()
        except Exception as e:
            logger.warning(f"DeepSeek suggestion failed: {e}")

    # Fall back to mock
    from services.ai_mock import get_ai_suggestion as mock_suggest
    logger.info("Using mock AI for suggestion")
    return await mock_suggest(prompt)


async def analyze_diagnosis_data(db: AsyncSession, diagnosis_json: str) -> dict:
    """
    Analyze a batch of diagnosis results using DeepSeek.
    Returns structured analysis: {summary, correct_rate, weak_kps, ...}
    """
    deepseek_config = await _get_config(db, "deepseek")
    if deepseek_config and deepseek_config.api_key and deepseek_config.is_active:
        try:
            cfg = PROVIDER_CONFIGS["deepseek"]
            base_url = deepseek_config.base_url or cfg["base_url"]
            model = deepseek_config.model_name or cfg["model"]

            result_text = await _call_deepseek(
                api_key=deepseek_config.api_key,
                base_url=base_url,
                model=model,
                system_prompt=DIAGNOSIS_ANALYSIS_PROMPT,
                user_message=f"请分析以下诊断数据：\n{diagnosis_json}",
                timeout=cfg["timeout"],
                temperature=0.5,
            )

            # Parse JSON response
            result_text = result_text.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1] if "\n" in result_text else result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
            return json.loads(result_text)
        except Exception as e:
            logger.warning(f"DeepSeek analysis failed: {e}")

    # Fallback: basic analysis from mock data
    return {
        "summary": "基于Mock AI的诊断分析（接入真实API后可获得详细分析）",
        "correct_rate": 0.5,
        "weak_kps": ["异分母分数加减", "分数应用题建模"],
        "common_errors": ["通分步骤缺失", "审题遗漏条件"],
        "recommendations": ["强化通分专项训练", "增加应用题建模练习"],
    }
