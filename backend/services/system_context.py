"""
System context provider — gives the AI Assistant knowledge about all modules,
their data schemas, and what statistics/queries are available.

This context is injected into every AI Assistant prompt so the LLM can
answer questions about the system's data accurately.
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# ═══════════════════════════════════════════════════════════
#  Static system description (injected into every prompt)
# ═══════════════════════════════════════════════════════════

SYSTEM_DESCRIPTION = """
## 系统概述
你是一个"AI学习诊断系统"的智能助手。该系统服务于中小学培训机构，帮助老师进行试卷批改、学情诊断和个性化练习管理。

## 系统模块与数据

### 1. 组织管理（年级/班级/老师/学生）
- **年级**（grades）：如五年级、六年级、初一、初二、初三等。字段：id, name, sort_order
- **班级**（classes）：如五(1)班。字段：id, name, grade_id（关联年级）, subjects（学科列表）, student_count（学生数）
- **老师**（users）：字段：name, phone, role（teacher/admin/research/super）, grades（负责年级）, subjects（学科）, class_ids（负责班级）
- **学生**（students）：字段：name, class_id（所属班级）, mastery（掌握度0-100）, trend（up/down/stable）, weak_points（薄弱知识点列表）

### 2. 任务管理
- **任务**（tasks）：老师创建的试卷批改任务。字段：name, type（周测/日常作业/阶段测等）, subject, grade, status（draft→pending_upload→ai_processing→pending_review→completed）, class_ids, pages, difficulty, kps（目标知识点）
- 任务状态流转：草稿→待上传→AI处理中→待确认→已完成

### 3. 上传与AI批改
- 老师上传标准答案图片和学生的试卷图片
- AI自动识别手写内容（GLM-4V多模态模型），逐题诊断
- 支持图片/PDF/Word上传（单文件≤50MB）

### 4. 诊断结果
- **诊断**（question_results）：每题一条记录。字段：task_id, student_id, question_number, verdict（correct/incorrect/partially_correct/uncertain）, ocr_text（识别文本）, kp_name（知识点）, error_cause（错因）, skill_cause（技能原因）, ai_confidence（AI置信度）, is_typical（是否典型错题）

### 5. 知识体系
- **知识点树**（knowledge_points）：自引用树形结构。字段：name, subject, grade, stage（小学/初中）, level（层级）, mastery（掌握度）, keywords

### 6. 练习计划
- **练习计划**（exercise_plans）：根据诊断结果为学生生成的个性化练习。字段：student_id, kp（目标知识点）, count（题量）, difficulty, frequency（频率）, effect（效果）

### 7. 题库管理
- **题目**（questions）：字段：title, type, subject, grade, difficulty, kp_id（关联知识点）, source（题源）

### 8. 诊断看板
- 按年级和学科展示知识点×学生热力图
- AI教学建议

### 9. 数据总览
- KPI卡片：学生总数、老师数、任务总数、待确认数
- 各年级知识点错误率柱状图
- 共同薄弱点TOP5

### 10. 系统管理（超级管理员）
- AI模型配置（GLM-4V / DeepSeek / OpenAI等）
- 错误日志查看与修复
- 权限配置
- 审计日志
- 远程协助
"""

# ═══════════════════════════════════════════════════════════
#  Dynamic queries — the AI can request these
# ═══════════════════════════════════════════════════════════

QUERY_TOOLS = [
    {
        "name": "get_system_stats",
        "description": "获取系统整体统计数据：学生总数、老师数、任务数、待确认数、平均掌握度、完成率",
        "parameters": {}
    },
    {
        "name": "get_grade_distribution",
        "description": "获取各年级学生人数和平均掌握度分布",
        "parameters": {}
    },
    {
        "name": "get_top_weaknesses",
        "description": "获取全班/全年级最薄弱的知识点TOP排行",
        "parameters": {"limit": "int (default 5)"}
    },
    {
        "name": "get_student_count",
        "description": "查询学生总人数或按年级/班级筛选",
        "parameters": {"grade": "str (optional)", "class_name": "str (optional)"}
    },
    {
        "name": "get_teacher_list",
        "description": "获取老师列表及其负责的年级和班级",
        "parameters": {}
    },
    {
        "name": "get_task_summary",
        "description": "获取任务状态汇总：各状态任务数量",
        "parameters": {}
    },
    {
        "name": "get_recent_diagnosis_summary",
        "description": "获取最近诊断结果的汇总：正确率、常见错因",
        "parameters": {"limit": "int (default 10)"}
    },
]


async def execute_query(db: AsyncSession, query_name: str, params: dict = None) -> dict:
    """Execute a named query against the database and return structured results."""
    params = params or {}

    if query_name == "get_system_stats":
        from models.student import Student
        from models.user import User
        from models.task import Task
        student_count = (await db.execute(select(func.count()).select_from(Student))).scalar()
        teacher_count = (await db.execute(select(func.count()).select_from(User).where(User.role == "teacher"))).scalar()
        task_count = (await db.execute(select(func.count()).select_from(Task))).scalar()
        pending = (await db.execute(
            select(func.count()).select_from(Task).where(Task.status.in_(["pending_review", "partial_confirmed"]))
        )).scalar()
        avg_m = (await db.execute(select(func.avg(Student.mastery)).select_from(Student))).scalar() or 0
        return {
            "学生总数": student_count,
            "老师数": teacher_count,
            "任务总数": task_count,
            "待确认任务": pending,
            "平均掌握度": f"{round(float(avg_m), 1)}%",
        }

    if query_name == "get_grade_distribution":
        from models.class_ import Class, Grade
        from models.student import Student
        grades = (await db.execute(select(Grade).order_by(Grade.sort_order))).scalars().all()
        result = {}
        for g in grades:
            cls_sub = select(Class.id).where(Class.grade_id == g.id)
            cnt = (await db.execute(select(func.count()).select_from(Student).where(Student.class_id.in_(cls_sub)))).scalar()
            avg_m = (await db.execute(select(func.avg(Student.mastery)).select_from(Student).where(Student.class_id.in_(cls_sub)))).scalar() or 0
            if cnt > 0:
                result[g.name] = f"{cnt}人, 平均掌握度{round(float(avg_m), 1)}%"
        return result

    if query_name == "get_top_weaknesses":
        from models.diagnosis import QuestionResult
        limit = int(params.get("limit", 5))
        rows = (await db.execute(
            select(QuestionResult.kp_name, func.count().label("cnt"))
            .where(QuestionResult.verdict == "incorrect", QuestionResult.kp_name != "")
            .group_by(QuestionResult.kp_name)
            .order_by(func.count().desc())
            .limit(limit)
        )).all()
        return {row[0]: f"{row[1]}次错误" for row in rows}

    if query_name == "get_student_count":
        from models.student import Student
        from models.class_ import Class, Grade
        query = select(func.count()).select_from(Student)
        grade_name = params.get("grade")
        class_name = params.get("class_name")
        if grade_name:
            grade_sub = select(Grade.id).where(Grade.name == grade_name)
            cls_sub = select(Class.id).where(Class.grade_id.in_(grade_sub))
            query = query.where(Student.class_id.in_(cls_sub))
        if class_name:
            cls_sub = select(Class.id).where(Class.name == class_name)
            query = query.where(Student.class_id.in_(cls_sub))
        count = (await db.execute(query)).scalar()
        desc = ""
        if grade_name: desc += grade_name
        if class_name: desc += class_name
        return {f"学生人数{f'（{desc}）' if desc else ''}": count}

    if query_name == "get_teacher_list":
        from models.user import User
        import json
        teachers = (await db.execute(
            select(User).where(User.role == "teacher")
        )).scalars().all()
        result = {}
        for t in teachers:
            grades = json.loads(t.grades) if t.grades else []
            result[t.name] = f"负责年级: {', '.join(grades) if grades else '未分配'}"
        return result

    if query_name == "get_task_summary":
        from models.task import Task
        statuses = ["draft", "pending_upload", "ai_processing", "pending_review", "completed"]
        result = {}
        for s in statuses:
            cnt = (await db.execute(select(func.count()).select_from(Task).where(Task.status == s))).scalar()
            status_names = {"draft": "草稿", "pending_upload": "待上传", "ai_processing": "AI处理中",
                           "pending_review": "待确认", "completed": "已完成"}
            result[status_names.get(s, s)] = cnt
        return result

    if query_name == "get_recent_diagnosis_summary":
        from models.diagnosis import QuestionResult
        limit = int(params.get("limit", 10))
        total = (await db.execute(select(func.count()).select_from(QuestionResult))).scalar()
        correct = (await db.execute(
            select(func.count()).select_from(QuestionResult).where(QuestionResult.verdict == "correct")
        )).scalar()
        return {
            "最近诊断总数": total,
            "正确率": f"{round(correct / max(total, 1) * 100, 1)}%",
            "说明": f"共{total}条诊断记录，{correct}条正确",
        }

    return {"error": f"未知查询: {query_name}"}
