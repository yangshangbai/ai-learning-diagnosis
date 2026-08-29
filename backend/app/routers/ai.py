"""AI 视觉识别接口：答题卡拍照 → 调用多模态模型（智谱 GLM-4V 等）识别学生与各题答案。

端点：
  POST /api/v1/ai/recognize-answer-sheet   识别答题卡图片 → 学生编码/姓名 + 各题答案

说明：
- 模型凭据由前端「系统设置→AI模型配置」明文保存，随请求传入（本环境无密钥库，前端本地工具）。
- 目前完整实现智谱 GLM-4V（open.bigmodel.cn）；其余 provider 返回明确提示，便于扩展。
"""
import json
import re
import urllib.request
from typing import Optional, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.errors import NotFoundError, ValidationError
from ..core.logging import logger
from ..core.security import Principal, require_auth, require_permission

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class RecognizeAnswerSheetBody(BaseModel):
    task_id: int
    image_base64: str  # data URL 或纯 base64
    provider: str = "zhipu"
    api_key: str = ""
    model: str = "glm-4v"


class RecognizedAnswer(BaseModel):
    question_number: int
    answer: str = ""


class RecognizeResult(BaseModel):
    student_code: Optional[str] = None
    student_name: Optional[str] = None
    answers: List[RecognizedAnswer] = []
    raw: Optional[str] = None


_TYPE_NAME = {
    "single_choice": "单选", "multi_choice": "多选", "fill_blank": "填空",
    "true_false": "判断", "essay": "解答",
}


def _build_prompt(pqs) -> str:
    """构造识别 prompt：告诉模型答题卡上有哪些题、要识别什么、按什么 JSON 输出。"""
    lines = [
        "你是一名考试答题卡智能识别助手。请仔细识别这张答题卡照片，提取信息：",
        "",
        "1. 学生信息：答题卡顶部机读带/二维码/手写区域的「学号」（如 A01）和「姓名」。",
        "2. 各题答案：按题号顺序，识别学生填涂的选项或书写/填写的答案。",
        "",
        "试卷题目清单（题号与答题区一一对应）：",
    ]
    for pq in pqs:
        q = pq["question"]
        tname = _TYPE_NAME.get(q.ques_type, q.ques_type)
        opts = ""
        if q.options:
            opts = " 选项: " + "  ".join(str(o) for o in q.options)
        lines.append(f"第{pq['sort_order']}题（{tname}）{opts}")
    lines += [
        "",
        "请严格只输出一个 JSON 对象（不要输出任何其他文字、解释、markdown 代码块标记），格式：",
        '{"student_code":"A01","student_name":"张三","answers":[{"question_number":1,"answer":"B"},{"question_number":2,"answer":"5"}]}',
        "规则：客观题 answer 只写选项字母（A/B/C/D，多选写如 AB）或判断结果（√/×/正确/错误）；",
        "填空题写填写内容；解答题写关键结果或步骤（无法识别则空字符串）。未作答或无法识别的题，answer 用空字符串。",
    ]
    return "\n".join(lines)


def _call_zhipu(api_key: str, model: str, image_base64: str, prompt: str) -> str:
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    # 兼容纯 base64（无 data: 前缀）与 data URL
    img_url = image_base64
    if not img_url.startswith("data:") and not img_url.startswith("http"):
        img_url = "data:image/png;base64," + image_base64
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": img_url}},
                {"type": "text", "text": prompt},
            ],
        }],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("choices"):
        raise ValidationError("模型未返回有效结果：" + json.dumps(data, ensure_ascii=False)[:300])
    return data["choices"][0]["message"]["content"] or ""


def _parse_json(text: str):
    """从模型输出中提取 JSON（容忍被 ```json``` 包裹、前后杂文、多段输出）。"""
    if not text:
        return {}
    t = text.strip()
    # 去除 ```json ... ``` 包裹
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", t)
    if m:
        t = m.group(1)
    # 1. 直接解析
    try:
        return json.loads(t)
    except Exception:
        pass
    # 2. 括号平衡匹配第一个完整 JSON 对象
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


@router.post("/recognize-answer-sheet", response_model=RecognizeResult)
def recognize_answer_sheet(body: RecognizeAnswerSheetBody, _: Principal = Depends(require_permission("ai", "add")), db: Session = Depends(get_db)):
    task = db.query(models.ExamTask).filter(models.ExamTask.id == body.task_id).first()
    if not task:
        raise NotFoundError("考试任务", body.task_id)
    if not body.image_base64:
        raise ValidationError("缺少答题卡图片")
    if not body.api_key:
        raise ValidationError("未配置 AI 模型 API Key（系统设置→AI模型配置）")

    paper = db.query(models.Paper).filter(models.Paper.id == task.paper_id).first()
    pqs = (
        db.query(models.PaperQuestion)
        .filter(models.PaperQuestion.paper_id == task.paper_id)
        .order_by(models.PaperQuestion.sort_order)
        .all()
    )
    if not pqs:
        raise ValidationError("任务关联试卷无题目")

    # 组装题目清单（用于对齐题号）
    pqs_info = []
    for pq in pqs:
        q = db.query(models.Question).filter(models.Question.id == pq.question_id).first() if pq.question_id else None
        pqs_info.append({"sort_order": pq.sort_order, "question": q})

    prompt = _build_prompt(pqs_info)

    if body.provider != "zhipu":
        raise ValidationError(f"当前仅支持智谱 GLM-4V 视觉识别（收到 provider={body.provider}）")

    raw = _call_zhipu(body.api_key, body.model, body.image_base64, prompt)
    data = _parse_json(raw)

    answers = []
    for a in data.get("answers") or []:
        try:
            answers.append(RecognizedAnswer(
                question_number=int(a.get("question_number") or 0),
                answer=str(a.get("answer") or ""),
            ))
        except (TypeError, ValueError):
            continue

    result = RecognizeResult(
        student_code=data.get("student_code"),
        student_name=data.get("student_name"),
        answers=answers,
        raw=raw,
    )
    logger.info("ai_recognize_done", extra={"task": body.task_id, "student": result.student_code, "n_answers": len(answers)})
    return result
