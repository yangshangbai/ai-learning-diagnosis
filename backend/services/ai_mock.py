"""Mock AI diagnosis service — delegates to ai_service when real API keys are available."""

import asyncio
import json
import random
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from models.diagnosis import QuestionResult

# ── Mock diagnosis templates matching the existing seed data ───────────────
MOCK_DIAGNOSES = [
    {
        "num": 1,
        "verdict": "correct",
        "ocrText": "3/8 + 2/8 = 5/8",
        "wrongStep": "无",
        "kp": "分数概念",
        "relatedKps": ["同分母分数加减"],
        "errorCause": "",
        "skillCause": "无",
        "ability": "概念理解能力",
        "aiExplain": "学生正确理解了分数基本概念，过程和结果均正确",
        "confidence": 0.95,
        "typical": False,
    },
    {
        "num": 2,
        "verdict": "correct",
        "ocrText": "7/9 - 2/9 = 5/9",
        "wrongStep": "无",
        "kp": "同分母分数加减",
        "relatedKps": ["分数概念"],
        "errorCause": "",
        "skillCause": "无",
        "ability": "运算能力",
        "aiExplain": "同分母计算扎实，分母保持不变、分子相减正确",
        "confidence": 0.93,
        "typical": False,
    },
    {
        "num": 3,
        "verdict": "incorrect",
        "ocrText": "1/3 + 1/2 = 2/5",
        "wrongStep": "未先通分，直接分子分母分别相加",
        "kp": "异分母分数加减",
        "relatedKps": ["通分", "分数基本性质"],
        "errorCause": "概念混淆",
        "skillCause": "程序性知识错误",
        "ability": "概念理解能力",
        "aiExplain": "未通分直接相加。正确做法应先通分为2/6+3/6=5/6",
        "confidence": 0.91,
        "typical": True,
    },
    {
        "num": 4,
        "verdict": "correct",
        "ocrText": "3/5 > 4/9",
        "wrongStep": "无",
        "kp": "分数比较",
        "relatedKps": ["通分"],
        "errorCause": "",
        "skillCause": "无",
        "ability": "逻辑推理能力",
        "aiExplain": "分数大小比较方法正确，能选择通分后比较",
        "confidence": 0.94,
        "typical": False,
    },
    {
        "num": 5,
        "verdict": "partially_correct",
        "ocrText": "1/8 = 0.12",
        "wrongStep": "小数换算末位漏写5",
        "kp": "分数与小数互化",
        "relatedKps": ["除法计算"],
        "errorCause": "计算失误",
        "skillCause": "S型-计算细节错误",
        "ability": "运算能力",
        "aiExplain": "思路正确，但1/8转化为小数时计算错误，应为0.125",
        "confidence": 0.87,
        "typical": False,
    },
    {
        "num": 6,
        "verdict": "incorrect",
        "ocrText": "剩下部分直接乘总量",
        "wrongStep": "遗漏题干中\"剩下的\"这一条件",
        "kp": "分数应用题建模",
        "relatedKps": ["单位1识别", "分数乘法"],
        "errorCause": "建模失败",
        "skillCause": "审题偏差",
        "ability": "应用建模能力",
        "aiExplain": "未能将实际问题转化为分数模型，审题遗漏关键条件",
        "confidence": 0.88,
        "typical": True,
    },
    {
        "num": 7,
        "verdict": "correct",
        "ocrText": "2/5 × 15 = 6",
        "wrongStep": "无",
        "kp": "分数乘法",
        "relatedKps": ["整数乘法"],
        "errorCause": "",
        "skillCause": "无",
        "ability": "运算能力",
        "aiExplain": "分数乘法运算正确，单位处理完整",
        "confidence": 0.96,
        "typical": False,
    },
    {
        "num": 8,
        "verdict": "incorrect",
        "ocrText": "先算加法再算乘法",
        "wrongStep": "四则混合运算顺序错误",
        "kp": "分数四则混合运算",
        "relatedKps": ["分数乘除法", "运算顺序"],
        "errorCause": "策略不当",
        "skillCause": "程序性知识错误",
        "ability": "逻辑推理能力",
        "aiExplain": "运算顺序错误，未按先乘除后加减的规则",
        "confidence": 0.92,
        "typical": True,
    },
    {
        "num": 9,
        "verdict": "correct",
        "ocrText": "x = 3/4",
        "wrongStep": "无",
        "kp": "分数方程",
        "relatedKps": ["等式性质"],
        "errorCause": "",
        "skillCause": "无",
        "ability": "表达规范能力",
        "aiExplain": "分数方程求解步骤完整正确，书写规范",
        "confidence": 0.90,
        "typical": False,
    },
    {
        "num": 10,
        "verdict": "uncertain",
        "ocrText": "字迹模糊，仅能识别部分步骤",
        "wrongStep": "关键列式区域无法识别",
        "kp": "综合应用题",
        "relatedKps": ["分数应用题建模", "审题能力"],
        "errorCause": "需人工判断",
        "skillCause": "低置信度-需人工补录",
        "ability": "审题能力",
        "aiExplain": "学生作答部分正确但字迹模糊，部分步骤难以确认",
        "confidence": 0.55,
        "typical": False,
    },
]


async def run_mock_ai_diagnosis(
    task_id: int,
    student_id: int,
    db: AsyncSession,
) -> list[QuestionResult]:
    """Simulate AI grading with varied results per student for realistic demo data."""
    await asyncio.sleep(random.uniform(0.5, 1.5))

    # Use student_id to seed variation — each student gets different results
    rng = random.Random(student_id * 31 + task_id * 7)

    # Student tier: 0=strong(70%+ correct), 1=average(50%), 2=weak(30%)
    tier = student_id % 3

    results = []
    for d in MOCK_DIAGNOSES:
        # Randomize verdict per student for realistic variation
        verdict = d["verdict"]
        roll = rng.random()

        if tier == 0:  # Strong student
            if roll < 0.72: verdict = "correct"
            elif roll < 0.88: verdict = "partially_correct"
            elif roll < 0.96: verdict = "incorrect"
            else: verdict = "uncertain"
        elif tier == 1:  # Average student
            if roll < 0.52: verdict = "correct"
            elif roll < 0.68: verdict = "partially_correct"
            elif roll < 0.88: verdict = "incorrect"
            else: verdict = "uncertain"
        else:  # Weak student
            if roll < 0.32: verdict = "correct"
            elif roll < 0.48: verdict = "partially_correct"
            elif roll < 0.85: verdict = "incorrect"
            else: verdict = "uncertain"

        # Adjust confidence based on verdict randomness
        confidence = d["confidence"]
        if verdict != d["verdict"]:
            confidence = round(rng.uniform(0.50, 0.88), 2)

        # Only mark as typical for tier 1-2 incorrect answers
        is_typical = verdict == "incorrect" and tier > 0 and rng.random() < 0.3

        result = QuestionResult(
            task_id=task_id,
            student_id=student_id,
            question_number=d["num"],
            verdict=verdict,
            ocr_text=d["ocrText"],
            wrong_step=d["wrongStep"] if verdict != "correct" else "无",
            kp_name=d["kp"],
            related_kps=json.dumps(d["relatedKps"], ensure_ascii=False),
            error_cause=d["errorCause"] if verdict != "correct" else "",
            skill_cause=d["skillCause"] if verdict != "correct" else "无",
            ability_dimension=d["ability"],
            ai_explain=d["aiExplain"],
            ai_confidence=confidence,
            ai_raw_json=json.dumps(d, ensure_ascii=False),
            is_typical=is_typical,
            created_at=datetime.utcnow(),
        )
        results.append(result)

    return results


async def get_ai_suggestion(prompt: str) -> str:
    """Simulate AI assistant response based on prompt keywords."""
    await asyncio.sleep(1.0)

    prompt_lower = prompt.lower()

    if "错题" in prompt or "错误" in prompt or "分析" in prompt:
        return (
            "根据AI诊断结果，该学生的主要问题集中在以下几个方面：\n"
            "1. 异分母分数加减法通分步骤缺失（第3、8题）\n"
            "2. 分数应用题建模能力不足，审题遗漏关键条件（第6题）\n"
            "3. 分数与小数互化计算细节错误（第5题）\n\n"
            "建议：优先强化通分专项训练，再进行综合应用题建模练习。"
        )
    elif "教学" in prompt or "建议" in prompt or "策略" in prompt:
        return (
            "针对班级整体情况的教学建议：\n"
            "1. 强化通分概念，通过可视化工具帮助学生理解\n"
            "2. 设计分层次的分数应用题，从单一条件逐步过渡到多条件\n"
            "3. 增加四则混合运算的顺序训练\n"
            "4. 对掌握度低于60%的知识点进行专项补救"
        )
    elif "练习" in prompt or "题目" in prompt or "推荐" in prompt:
        return (
            "推荐练习方案：\n"
            "1. 异分母分数加减专项 - 每天10题，连续3天\n"
            "2. 分数应用题建模 - 每周3次，每次5题\n"
            "3. 四则混合运算顺序 - 每周2次，每次8题\n"
            "预计2周内可将相关知识点掌握度提升至75%以上。"
        )
    elif "报告" in prompt or "总结" in prompt:
        return (
            "AI诊断报告总结：\n"
            "本次共诊断10道题目，正确5题，部分正确1题，错误3题，不确定1题。\n"
            "整体正确率50%，AI置信度平均87.1%。\n"
            "典型错例2道（第3、8题），建议标记为班级共性错因。\n"
            "核心薄弱点：异分母分数加减（通分策略不当）。"
        )
    else:
        return (
            "根据当前数据，建议关注以下方面：\n"
            "1. 重点知识点掌握度趋势\n"
            "2. 班级共性错因分布\n"
            "3. 学生个性化薄弱点\n"
            "4. 与上次诊断结果的对比变化"
        )
