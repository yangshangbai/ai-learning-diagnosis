"""AI 选题同步：提示词 → AI 拆解查询任务 → 循环查教研云 → AI 分析选题 → 落表 → 用户确认后同步系统题库。

端点：
  POST /api/v1/ai/select-questions         AI 选题（拆解+查询+分析+落表）
  GET  /api/v1/ai/selections                AI 选题库列表（分页）
  GET  /api/v1/ai/selections/{id}           选题详情
  POST /api/v1/ai/selections/{id}/confirm   确认同步到系统题库（questions）
"""
import json
import os
import re
import urllib.request
import urllib.parse
import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.config import settings
from ..core.errors import NotFoundError, ValidationError
from ..core.logging import logger
from ..core.security import Principal, require_auth, require_permission
from .question import generate_question_code

router = APIRouter(prefix="/api/v1/ai", tags=["ai-select"])

# 教研云本地代理（本机 :8787，live 走 Chrome，offline 走本地缓存）
JIAOYANYUN = "http://127.0.0.1:8787"
# 教研云代理开关：云端无代理时置 0，AI 选题直接走系统题库
JIAOYANYUN_ENABLED = os.getenv("JIAOYANYUN_PROXY_ENABLED", "1") != "0"
# 注意：SUBJECT_ID 是【教研云的学科 id】，仅用于给教研云查询接口拼 subjectId 参数，
# 绝不能直接当系统 categories.id 使用（系统学科 id：数学1/语文2/英语3/物理4/化学5）。
# 把教研云题目落库到 questions.subject_id 时，一律走 confirm_selection 的 _cat_id 按名称解析。
SUBJECT_ID = {'数学': '2', '语文': '1', '英语': '3', '物理': '4', '化学': '5', '生物': '6'}
GRADE_GROUP_ID = {'小学': '1', '初中': '2', '高中': '3', '大学': '4'}
# 教研云题型 id（writtenQuesTypes）
WQT_ID = {
    'single_choice': '13f97b02f7e4f2c9d35ec1af3c2d1018',   # 单选
    'multi_choice': '171d0892c80040fa8e19c7ca326a92d1',    # 多选
    'fill_blank': '13f97b02f7e4f2c9d35ec1af3c2d1019',       # 填空
    'true_false': '13f97b02f7e4f2c9d35ce1af3c2d1022',       # 判断
    'essay': '13f97b02f7e4f2c9d35ec1af3c2d1020',            # 解答题
}
# 难度占比 → 教研云难度编号（1易 2较易 3中档 4较难 5难）
DIFF_RATIO_MAP = {
    'easy': [1, 2], 'medium': [3], 'hard': [4, 5],
}

# 教研云 map_type 简写 → 本系统 ques_type 标准值
TYPE_MAP = {
    'single': 'single_choice', 'single_choice': 'single_choice',
    'multi': 'multi_choice', 'multi_choice': 'multi_choice',
    'judge': 'true_false', 'true_false': 'true_false',
    'fill': 'fill_blank', 'fill_blank': 'fill_blank',
    'essay': 'essay', 'experiment': 'essay', 'composition': 'essay', 'reading': 'essay',
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SelectQuestionsBody(BaseModel):
    title: str = ""
    subject_name: str = "数学"
    grade_group_name: str = "初中"
    grade_name: str = ""
    semester: str = ""
    category: str = ""
    type_config: dict = {}          # {single_choice:3, fill_blank:2, essay:2}
    difficulty_ratio: dict = {}     # {easy:30, medium:50, hard:20}
    provider: str = "deepseek"
    api_key: str = ""
    model: str = "deepseek-chat"   # V4 Flash 非思考模式：AI 选题拆解/选题快且稳


# ---------------- 文本推理模型调用（多 provider） ----------------
# OpenAI 兼容接口的 provider 端点表
_TEXT_PROVIDERS = {
    "deepseek": "https://api.deepseek.com/chat/completions",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "moonshot": "https://api.moonshot.cn/v1/chat/completions",
}


def _call_text_llm(provider: str, api_key: str, model: str, prompt: str) -> str:
    """调用文本推理模型（OpenAI 兼容 /chat/completions），返回消息内容。"""
    url = _TEXT_PROVIDERS.get(provider)
    if not url:
        raise ValidationError(f"不支持的推理模型 provider：{provider}")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 3000,   # 防止思考模式(reasoning)吃掉全部 token 导致 content 为空
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("choices"):
        raise ValidationError("模型未返回有效结果")
    return data["choices"][0]["message"]["content"] or ""


def _parse_json(text: str):
    if not text:
        return {}
    t = text.strip()
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", t)
    if m:
        t = m.group(1)
    try:
        return json.loads(t)
    except Exception:
        pass
    start = t.find("{")
    if start < 0:
        return {}
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except Exception:
                    return {}
    return {}


# ---------------- 教研云查询 ----------------
def _query_jiaoyanyun(keyword, wqt_id, diff_id, subject_name, grade_group_name, page_size=20):
    sid = SUBJECT_ID.get(subject_name, '2')
    gid = GRADE_GROUP_ID.get(grade_group_name, '2')
    params = {
        "subjectId": sid, "gradeGroupId": gid,
        "subjectName": subject_name, "gradeGroupName": grade_group_name,
        "keyword": keyword or "",
        "writtenQuesTypeId": wqt_id or "",
        "difficultyId": diff_id or "",
        "pageNo": "1", "pageSize": str(page_size),
    }
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(JIAOYANYUN + "/api/search?" + qs)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("questions") or []


# 教研云题型 id -> 系统题型
_WQT_REV = {v: k for k, v in WQT_ID.items()}


def _query_local_bank(db, keyword, qtype, diff_id, subject_name, grade_name, limit=20):
    """从系统题库（questions 表）按 题型+难度+学科+年级+关键词 查询候选。
    云端无教研云代理时回退用；返回教研云同构 dict（queId 用 local-{id}）。
    条件从严到宽（关键词→年级→难度）渐进放宽，保证候选不空。"""
    qtype = qtype or "essay"

    def _base():
        q = db.query(models.Question).filter(models.Question.ques_type == qtype)
        if diff_id:
            try:
                q = q.filter(models.Question.difficulty == int(diff_id))
            except (ValueError, TypeError):
                pass
        if subject_name:
            c = db.query(models.Category).filter(
                models.Category.name == subject_name, models.Category.category_type == "subject"
            ).first()
            if c:
                q = q.filter(models.Question.subject_id == c.id)
        return q

    def _with_grade(q):
        if grade_name:
            g = db.query(models.Category).filter(
                models.Category.name == grade_name, models.Category.category_type == "grade"
            ).first()
            if g:
                return q.filter(models.Question.grade_id == g.id)
        return q

    def _with_kw(q):
        if keyword:
            kw = f"%{keyword}%"
            return q.filter(or_(models.Question.stem.ilike(kw), models.Question.analysis.ilike(kw)))
        return q

    # 从严到宽收集（按 id 去重）
    found = {}
    stages = [
        _with_kw(_with_grade(_base())),   # 关键词+年级
        _with_grade(_base()),             # 仅年级
        _with_kw(_base()),                # 仅关键词
        _base(),                          # 仅题型+学科
    ]
    for q in stages:
        for r in q.order_by(models.Question.id.desc()).limit(limit).all():
            if r.id not in found:
                found[r.id] = r
        if len(found) >= limit:
            break

    out = []
    for r in found.values():
        out.append({
            "queId": f"local-{r.id}",
            "positionCode": r.question_code or "",
            "stem": r.stem or "",
            "options": r.options or [],
            "answer": r.answer or "",
            "analysis": r.analysis or "",
            "difficulty": r.difficulty or 3,
            "type": r.ques_type or "essay",
            "writtenType": r.ques_type or "essay",
            "score": r.score or 5,
        })
    return out


def _strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "")


def _field_str(v):
    """把教研云任意类型字段归一化为字符串。

    - list（含嵌套）递归拍平，换行分隔；解决 answer/analysis/stem 被 str() 成
      "{'content': ...}" / "[object Object]" 的问题
    - dict 优先取 content/text/value/name 等承载正文的字段，避免对象被直接字符串化
    - 其余类型原样转 str
    """
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        parts = [_field_str(x) for x in v if x not in (None, "")]
        return "\n".join(p for p in parts if p)
    if isinstance(v, dict):
        for k in ("content", "text", "value", "html", "name", "stem"):
            if v.get(k):
                return _field_str(v[k])
        return json.dumps(v, ensure_ascii=False)
    return str(v)


# ---------------- AI 拆解查询任务 ----------------
def _ai_plan(body: SelectQuestionsBody) -> List[dict]:
    """AI 根据提示词 + 题型题量 + 难度占比，拆解出查询任务列表。失败则用默认计划。"""
    type_config = body.type_config or {}
    diff_ratio = body.difficulty_ratio or {}
    prompt = (
        "你是教研选题助手。用户要出一份试卷，请把需求拆解成多个题库查询任务，便于逐批检索后拼装。\n"
        f"用户提示词：{body.title or '（无）'}\n"
        f"学科：{body.subject_name}，年级：{body.grade_group_name}\n"
        f"各题型题量：{json.dumps(type_config, ensure_ascii=False)}\n"
        f"难度占比（easy容易/medium中等/hard困难）：{json.dumps(diff_ratio, ensure_ascii=False)}\n\n"
        "题型取值：single_choice单选 / multi_choice多选 / fill_blank填空 / true_false判断 / essay解答。\n"
        "难度编号：1容易 2较易 3中等 4较难 5困难。\n\n"
        "请严格只输出一个 JSON 对象（不要任何其他文字、解释、markdown 标记）：\n"
        '{"queries":[{"keyword":"有理数运算","type":"single_choice","difficulty":[1,2,3],"count":3}]}\n'
        "每个查询任务给出 keyword（检索关键词，可结合提示词提炼）、type、difficulty（编号数组）、count（题量）。"
    )
    if not body.api_key:
        return _default_plan(type_config, diff_ratio)
    try:
        raw = _call_text_llm(body.provider, body.api_key, body.model, prompt)
        data = _parse_json(raw)
        queries = data.get("queries") or []
        if not queries:
            return _default_plan(type_config, diff_ratio)
        out = []
        for q in queries:
            try:
                out.append({
                    "keyword": str(q.get("keyword") or ""),
                    "type": str(q.get("type") or ""),
                    "difficulty": [int(x) for x in (q.get("difficulty") or [])],
                    "count": int(q.get("count") or 3),
                })
            except (TypeError, ValueError):
                continue
        return out or _default_plan(type_config, diff_ratio)
    except Exception:
        return _default_plan(type_config, diff_ratio)


def _default_plan(type_config, diff_ratio):
    """降级：按题型题量 + 难度占比生成默认查询计划。"""
    plan = []
    for t, n in (type_config or {}).items():
        if not n:
            continue
        # 按难度占比拆分 count
        easy_n = max(1, round(n * (diff_ratio.get('easy', 30) / 100)))
        med_n = max(1, round(n * (diff_ratio.get('medium', 50) / 100)))
        hard_n = max(0, n - easy_n - med_n)
        if easy_n:
            plan.append({"keyword": "", "type": t, "difficulty": [1, 2], "count": easy_n})
        if med_n:
            plan.append({"keyword": "", "type": t, "difficulty": [3], "count": med_n})
        if hard_n:
            plan.append({"keyword": "", "type": t, "difficulty": [4, 5], "count": hard_n})
    return plan


# ---------------- AI 选题 ----------------
def _ai_pick(body: SelectQuestionsBody, candidates: List[dict]) -> List[str]:
    """AI 从候选题中选出最符合提示词的题目，返回选中的 queId 列表。失败则按顺序截取。"""
    type_config = body.type_config or {}
    total_want = sum(int(v) for v in type_config.values() if v) or len(candidates)
    if not candidates:
        return []
    if not body.api_key:
        return [c.get("queId") for c in candidates[:total_want] if c.get("queId")]
    # 候选描述（限制数量，避免 prompt 过长）
    shown = candidates[:40]
    lines = []
    for i, c in enumerate(shown):
        lines.append(
            f"{i}. [queId={c.get('queId')}] 题型={c.get('writtenType') or c.get('type')} "
            f"难度={c.get('difficulty')} 题干={_strip_html(c.get('stem'))[:80]}"
        )
    prompt = (
        "你是教研选题专家。请从下列候选题目中，选出最符合用户需求的最合适题目。\n"
        f"用户需求：{body.title or '（无）'}\n"
        f"各题型题量：{json.dumps(type_config, ensure_ascii=False)}\n\n"
        "候选题目：\n" + "\n".join(lines) + "\n\n"
        f"请严格只输出一个 JSON 对象（不要任何其他文字）：\n"
        f'{{"picked":["queId1","queId2",...],"reason":"选这些题的理由"}}\n'
        f"共选 {total_want} 道，尽量满足题型题量，优先与需求语义最贴切的题。"
    )
    try:
        raw = _call_text_llm(body.provider, body.api_key, body.model, prompt)
        data = _parse_json(raw)
        picked = data.get("picked") or []
        ids = [str(x) for x in picked]
        # 保留候选顺序，去重
        ordered = [c.get("queId") for c in candidates if str(c.get("queId")) in ids]
        seen = set()
        result = []
        for qid in ordered:
            if qid not in seen:
                seen.add(qid)
                result.append(qid)
        # AI 选不满时按候选顺序补齐（保证达到 total_want）
        for c in candidates:
            qid = c.get("queId")
            if qid and qid not in seen:
                seen.add(qid)
                result.append(qid)
            if len(result) >= total_want:
                break
        return result[:total_want]
    except Exception:
        return [c.get("queId") for c in candidates[:total_want] if c.get("queId")]


# ---------------- 端点 ----------------
@router.post("/select-questions")
def select_questions(body: SelectQuestionsBody, principal: Principal = Depends(require_permission("ai_select", "add")), db: Session = Depends(get_db)):
    if not body.api_key and not settings.ai_zhipu_api_key:
        raise ValidationError("未配置 AI 模型 API Key（系统设置→AI模型配置，或服务端 AI_ZHIPU_API_KEY）")
    if not body.api_key:
        # 服务端统一密钥：推理模型切换为智谱文本模型（服务端仅托管智谱 Key）
        body.provider = "zhipu"
        if "deepseek" in (body.model or "") or not (body.model or ""):
            body.model = "glm-4-flash"
        body.api_key = settings.ai_zhipu_api_key
    if not body.type_config:
        raise ValidationError("请设置各题型题量")

    # 1. AI 拆解查询任务
    plan = _ai_plan(body)

    # 2. 循环查教研云（按计划，去重）；代理不可用/候选不足时回退系统题库
    candidates = []
    seen = set()
    for q in plan:
        t = q.get("type")
        wqt_id = WQT_ID.get(t, "")
        for d in (q.get("difficulty") or []):
            if JIAOYANYUN_ENABLED:
                try:
                    items = _query_jiaoyanyun(q.get("keyword"), wqt_id, str(d), body.subject_name, body.grade_group_name)
                    for c in items:
                        qid = c.get("queId") or c.get("positionCode")
                        if qid and qid not in seen:
                            seen.add(qid)
                            candidates.append(c)
                except Exception as e:
                    logger.warning("ai_select_query_fail", extra={"type": t, "diff": d, "err": str(e)})
            # 系统题库回退补充（云端无教研云代理也能选题）
            try:
                local = _query_local_bank(db, q.get("keyword"), t, d, body.subject_name, body.grade_name)
                for c in local:
                    qid = c.get("queId")
                    if qid and qid not in seen:
                        seen.add(qid)
                        candidates.append(c)
            except Exception as e:
                logger.warning("ai_select_local_fail", extra={"err": str(e)})
            if len(candidates) >= 60:
                break
        if len(candidates) >= 60:
            break

    # 3. AI 选题
    picked_ids = _ai_pick(body, candidates)
    picked_map = {str(c.get("queId")): c for c in candidates}
    picked = []
    for qid in picked_ids:
        c = picked_map.get(str(qid)) or picked_map.get(qid)
        if c:
            picked.append(c)

    # 4. 落表
    total_score = sum(int(c.get("score") or 0) for c in picked) or (len(picked) * 5)
    bank = models.AiSelectionBank(
        user_id=principal.user_id,
        title=body.title,
        subject_name=body.subject_name,
        grade_group_name=body.grade_group_name,
        grade_name=body.grade_name,
        semester=body.semester,
        category=body.category,
        type_config=body.type_config,
        difficulty_ratio=body.difficulty_ratio,
        plan=plan,
        questions=picked,
        total_score=total_score,
        status="draft",
    )
    db.add(bank)
    db.commit()
    db.refresh(bank)

    logger.info("ai_select_done", extra={"bank_id": bank.id, "picked": len(picked), "candidates": len(candidates)})
    return {
        "bank_id": bank.id,
        "title": bank.title,
        "plan": plan,
        "candidate_count": len(candidates),
        "picked": picked,
        "total": len(picked),
        "total_score": total_score,
    }


def _bank_out(b: models.AiSelectionBank) -> dict:
    return {
        "id": b.id,
        "title": b.title,
        "subject_name": b.subject_name,
        "grade_group_name": b.grade_group_name,
        "grade_name": b.grade_name,
        "semester": b.semester,
        "category": b.category,
        "type_config": b.type_config,
        "difficulty_ratio": b.difficulty_ratio,
        "plan": b.plan,
        "questions": b.questions or [],
        "total": len(b.questions or []),
        "total_score": b.total_score,
        "status": b.status,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


@router.get("/selections")
def list_selections(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    principal: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    q = db.query(models.AiSelectionBank)
    if principal.role != "admin":
        q = q.filter(models.AiSelectionBank.user_id == principal.user_id)
    total = q.count()
    rows = q.order_by(desc(models.AiSelectionBank.id)).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_bank_out(b) for b in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/selections/{bank_id}")
def get_selection(bank_id: int, principal: Principal = Depends(require_auth), db: Session = Depends(get_db)):
    b = db.query(models.AiSelectionBank).filter(models.AiSelectionBank.id == bank_id).first()
    if not b:
        raise NotFoundError("AI 选题", bank_id)
    return _bank_out(b)


@router.post("/selections/{bank_id}/confirm")
def confirm_selection(bank_id: int, principal: Principal = Depends(require_permission("ai_select", "edit")), db: Session = Depends(get_db)):
    """确认后把 AI 选题库的题目同步到系统题库（questions），并标记 synced。"""
    b = db.query(models.AiSelectionBank).filter(models.AiSelectionBank.id == bank_id).first()
    if not b:
        raise NotFoundError("AI 选题", bank_id)
    if not b.questions:
        raise ValidationError("该选题库无题目，无法同步")

    # 学科/年级 category_id 查找（用于 questions.subject_id / grade_id）
    def _cat_id(name, ctype):
        if not name:
            return None
        c = db.query(models.Category).filter(models.Category.name == name, models.Category.category_type == ctype).first()
        return c.id if c else None

    # 每题学科：优先取题目自身学科名（教研云 subjectName，反映题目真实学科），
    # 解析不到再回退选题库整体学科。避免教研云搜索结果不纯时把其它学科题标成用户所选学科。
    def _q_subject_id(q):
        for name in (q.get("subjectName"), q.get("subject_name"), b.subject_name):
            sid = _cat_id(name, "subject")
            if sid:
                return sid
        return None

    subject_id = _cat_id(b.subject_name, "subject")
    grade_id = _cat_id(b.grade_name, "grade") or _cat_id(b.grade_group_name, "grade")

    created = 0
    skipped = 0
    for i, q in enumerate(b.questions, 1):
        src = str(q.get("queId") or q.get("positionCode") or "")
        # 本地题库回退题（queId=local-{id}）：系统题库已存在该 id，直接复用，不重复插入
        if src.startswith("local-"):
            try:
                lid = int(src.split("-")[1])
            except (TypeError, ValueError):
                lid = None
            if lid is not None:
                exists = db.query(models.Question).filter(models.Question.id == lid).first()
                if exists:
                    skipped += 1
                    continue
        source_id = src
        # 已存在则跳过（按 source_id 去重）
        if source_id:
            exists = db.query(models.Question).filter(models.Question.source_id == source_id).first()
            if exists:
                skipped += 1
                continue
        # 答案：递归拍平（兼容 [["D"]]、["<p>...</p>"]、对象数组），保留 HTML；answer 缺失时用 normalAnswer 兜底
        ans_raw = q.get("answer") or q.get("normalAnswer") or []
        ans_text = _field_str(ans_raw)
        # 选项：统一为字符串数组 "A. 内容"（保留内容 HTML），避免前端把 {label,content} 对象
        # 字符串化渲染成 "[object Object]"
        opts = q.get("options") or []
        if isinstance(opts, list):
            norm_opts = []
            for idx, o in enumerate(opts):
                if isinstance(o, dict):
                    label = str(o.get("label") or chr(65 + idx))
                    content = _field_str(o.get("content") or "")
                    norm_opts.append(f"{label}. {content}".strip() if content else label)
                else:
                    norm_opts.append(_field_str(o))
            opts = norm_opts
        else:
            opts = None
        # 位置编码：优先用教研云 positionCode，冲突/缺失则按系统规则生成
        pos_code = str(q.get("positionCode") or q.get("code") or "").strip()
        if pos_code:
            code_exists = db.query(models.Question).filter(models.Question.question_code == pos_code).first()
            if code_exists:
                pos_code = ""
        if not pos_code:
            # 先 flush：让本轮已 add 的行对 generate_question_code 可见，避免多条撞同一编码
            db.flush()
            try:
                pos_code = generate_question_code(db, subject_id, grade_id, None)
            except Exception:
                pos_code = ""
        question = models.Question(
            question_code=pos_code or None,
            source="jiaoyanyun",
            source_id=source_id,
            subject_id=_q_subject_id(q),
            grade_id=grade_id,
            ques_type=TYPE_MAP.get(q.get("type"), q.get("type") or "essay"),
            difficulty=int(q.get("difficulty") or 3),
            # stem/analysis 保留完整 HTML（含 MathJax <svg> 公式）：若用 _strip_html 剥标签，
            # 会把 <title>\bigtriangleup</title> 的 LaTeX 裸文本漏进题干/解析，形成乱码。
            # 前端详情页按 HTML 渲染时 SVG 公式可正常显示。
            stem=_field_str(q.get("stem") or ""),
            options=opts or None,
            answer=ans_text,
            analysis=_field_str(q.get("analysis") or "") or ans_text,
            score=int(q.get("score") or 5),
        )
        db.add(question)
        created += 1

    b.status = "synced"
    db.commit()
    logger.info("ai_select_synced", extra={"bank_id": bank_id, "created_count": created, "skipped": skipped})
    return {"code": 0, "message": "synced", "data": {"bank_id": bank_id, "created": created, "skipped": skipped}}
