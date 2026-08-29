"""考试任务与 AI 评分接口。

端点：
  GET    /api/v1/exam-tasks                 列表（教师限自己创建）
  GET    /api/v1/exam-tasks/{id}            详情
  POST   /api/v1/exam-tasks                 新建（creator_id=教师；可同时分配学生）
  PUT    /api/v1/exam-tasks/{id}            更新
  DELETE /api/v1/exam-tasks/{id}            删除（真删除 + 级联清理下游数据）
  POST   /api/v1/exam-tasks/{id}/assign     分配学生（student_ids[]）
  GET    /api/v1/exam-tasks/{id}/assignments  分配列表
  POST   /api/v1/exam-tasks/{id}/answer-sheets  上传答题卡
  GET    /api/v1/exam-tasks/{id}/answer-sheets  答题卡列表
  POST   /api/v1/exam-tasks/answer-sheets/{id}/score   AI 评分（桩，待接入 Qwen-VL）
  PATCH  /api/v1/exam-tasks/question-scores/{id}       教师调分
  GET    /api/v1/exam-tasks/{id}/dashboard  全景统计

任务编码 §6.2：T + YYYYMMDD + 3 位流水。
状态机六态：draft/pending/in_exam/scoring/completed/voided。
权限：教师仅可访问自己创建的任务；管理员全量。
"""
import datetime
import html
import re
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from .. import models
from ..answer_sheet_renderer import render_multi_sheet_html
from ..core.db import SessionLocal
from ..core.errors import NotFoundError, ValidationError, ConflictError, ForbiddenError
from ..core.logging import logger
from ..core.security import Principal, require_auth, require_permission
from .paper import _download_response, _ensure_paper_template
from ..schemas.exam import (
    ExamTaskCreate,
    ExamTaskOut,
    ExamTaskUpdate,
    PaginatedExamTask,
    TaskAssignmentOut,
    AnswerSheetCreate,
    AnswerSheetOut,
    QuestionScoreUpdate,
    QuestionScoreOut,
    ExamDashboardOut,
)

router = APIRouter(prefix="/api/v1/exam-tasks", tags=["exam-task"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_task_code(db: Session) -> str:
    d = datetime.datetime.now().strftime("%Y%m%d")
    prefix = f"T{d}-"
    rows = db.query(models.ExamTask).filter(models.ExamTask.task_code.like(f"{prefix}%")).all()
    max_seq = 0
    for r in rows:
        try:
            seq = int(r.task_code.split("-")[-1])
            max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            continue
    if max_seq >= 999:
        raise ConflictError("任务编号已用完(999)")
    return f"{prefix}{max_seq + 1:03d}"


def _assign(db: Session, task_id: int, student_ids: List[int]):
    for sid in student_ids:
        stu = db.query(models.Student).filter(models.Student.id == sid).first()
        if not stu:
            continue
        db.add(
            models.TaskAssignment(
                task_id=task_id, student_id=sid, class_id=stu.class_id, status="pending"
            )
        )
    db.commit()


def _ensure_task_owner(db: Session, task: models.ExamTask, principal: Principal) -> None:
    """水平越权防护：教师仅可操作自己创建的任务（管理员全量）。"""
    if principal.role == "teacher" and principal.teacher_id != task.creator_id:
        raise ForbiddenError("仅可操作自己创建的任务")


_TF_MAP = {
    "√": "T", "对": "T", "正确": "T", "T": "T", "Y": "T", "YES": "T",
    "×": "F", "错": "F", "错误": "F", "F": "F", "N": "F", "NO": "F",
}


def _normalize_answer(value) -> str:
    """判分归一化：剥离HTML标签+还原实体（导入题标准答案常为 <p>..</p> 富文本，可双重转义）+去空白+大写。"""
    s = str(value or "")
    for _ in range(3):
        prev = s
        s = re.sub(r"<[^>]+>", "", s)
        s = html.unescape(s)
        if s == prev:
            break
    return re.sub(r"\s+", "", s).upper()


def _grade_objective(ques_type: Optional[str], student_answer: str, answer_key) -> Optional[bool]:
    """客观题确定性判分：与标准答案归一化比对。

    返回 True/False；主观题(essay)返回 None，交给教师评分。
    标准答案支持多可接受值（| 或 ｜ 或 「或」 分隔）。
    """
    qtype = ques_type or "essay"
    if qtype == "essay":
        return None
    sa = _normalize_answer(student_answer)
    keys = [
        _normalize_answer(k)
        for k in re.split(r"[|｜]|或", str(answer_key or ""))
        if str(answer_key or "").strip()
    ]
    if qtype == "multi_choice":
        sa = "".join(sorted(sa))
        keys = ["".join(sorted(k)) for k in keys]
    if qtype == "true_false":
        sa = _TF_MAP.get(sa, sa)
        keys = [_TF_MAP.get(k, k) for k in keys]
    return bool(sa) and sa in keys


def _persist_recognized_answers(db: Session, sheet: models.AnswerSheet, answers) -> bool:
    """识别答案随上传入库，并对客观题做服务端确定性判分（识别↔评分在此接通）。

    主观题(essay)不自动判分，留待教师。返回是否存在未判分题目。
    """
    task = db.query(models.ExamTask).filter(models.ExamTask.id == sheet.task_id).first()
    pqs = (
        db.query(models.PaperQuestion)
        .filter(models.PaperQuestion.paper_id == task.paper_id)
        .order_by(models.PaperQuestion.sort_order)
        .all()
    )
    amap = {a.question_number: str(a.answer or "") for a in answers if getattr(a, "question_number", None)}
    has_ungraded = False
    for pq in pqs:
        q = (
            db.query(models.Question).filter(models.Question.id == pq.question_id).first()
            if pq.question_id
            else None
        )
        qtype = q.ques_type if q else "essay"
        ans = amap.get(pq.sort_order, "")
        correct = pq.answer_key if pq.answer_key is not None else (q.answer if q else None)
        max_score = pq.score or 0
        ok = _grade_objective(qtype, ans, correct)
        if ok is None:
            has_ungraded = True
            ai_score = final = conf = None
            expl = "主观题，待教师评分"
        else:
            ai_score = float(max_score) if ok else 0.0
            final = ai_score
            conf = 1.0
            expl = "客观题自动判分（与标准答案归一化比对）"
            if qtype == "fill_blank" and not ok:
                expl += "；未命中任何可接受答案，建议人工复核"
        db.add(
            models.QuestionScore(
                answer_sheet_id=sheet.id,
                task_id=sheet.task_id,
                student_id=sheet.student_id,
                paper_question_id=pq.id,
                question_number=pq.sort_order,
                student_answer=ans,
                correct_answer=correct,
                ai_score=ai_score,
                ai_max_score=max_score,
                ai_confidence=conf,
                ai_explanation=expl,
                ai_raw_output={"grader": "server-objective-v1"},
                final_score=final,
                score_status="ai_scored",
            )
        )
    db.commit()
    return has_ungraded


def _to_task_out(db: Session, t: models.ExamTask) -> ExamTaskOut:
    out = ExamTaskOut.model_validate(t)
    paper = db.query(models.Paper).filter(models.Paper.id == t.paper_id).first()
    out.paper_name = paper.name if paper else None
    if t.creator_id:
        teacher = db.query(models.Teacher).filter(models.Teacher.id == t.creator_id).first()
        out.creator_name = teacher.name if teacher else None
    if t.category_id:
        cat = db.query(models.Category).filter(models.Category.id == t.category_id).first()
        out.category = cat.name if cat else None
    cnt = db.query(func.count(models.TaskAssignment.id)).filter(models.TaskAssignment.task_id == t.id).scalar() or 0
    out.student_count = cnt
    # 任务关联班级 id 数组（从 TaskAssignment 聚合 distinct class_id）
    cids = (
        db.query(models.TaskAssignment.class_id)
        .filter(models.TaskAssignment.task_id == t.id, models.TaskAssignment.class_id.isnot(None))
        .distinct()
        .all()
    )
    out.class_ids = [c[0] for c in cids]
    return out


@router.get("", response_model=PaginatedExamTask)
def list_tasks(
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    principal: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    query = db.query(models.ExamTask)
    if principal.role == "teacher":
        query = query.filter(models.ExamTask.creator_id == principal.teacher_id)
    if q:
        query = query.filter(models.ExamTask.name.ilike(f"%{q}%"))
    total = query.count()
    rows = (
        query.order_by(desc(models.ExamTask.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedExamTask(
        items=[_to_task_out(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}", response_model=ExamTaskOut)
def get_task(task_id: int, principal: Principal = Depends(require_auth), db: Session = Depends(get_db)):
    t = db.query(models.ExamTask).filter(models.ExamTask.id == task_id).first()
    if not t:
        raise NotFoundError("考试任务", task_id)
    if principal.role == "teacher" and principal.teacher_id != t.creator_id:
        raise ForbiddenError("仅可访问自己创建的任务")
    return _to_task_out(db, t)


@router.post("", response_model=ExamTaskOut, status_code=201)
def create_task(body: ExamTaskCreate, principal: Principal = Depends(require_permission("exam", "add")), db: Session = Depends(get_db)):
    paper = db.query(models.Paper).filter(models.Paper.id == body.paper_id).first()
    if not paper:
        raise NotFoundError("试卷", body.paper_id)
    code = generate_task_code(db)
    creator_id = principal.teacher_id if principal.role == "teacher" else None
    t = models.ExamTask(
        task_code=code,
        name=body.name,
        paper_id=body.paper_id,
        category_id=body.category_id,
        creator_id=creator_id,
        status="draft",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    if body.student_ids:
        _assign(db, t.id, body.student_ids)
    logger.info("exam_task_created", extra={"id": t.id, "code": code})
    return _to_task_out(db, t)


@router.put("/{task_id}", response_model=ExamTaskOut)
def update_task(task_id: int, body: ExamTaskUpdate, principal: Principal = Depends(require_permission("exam", "edit")), db: Session = Depends(get_db)):
    t = db.query(models.ExamTask).filter(models.ExamTask.id == task_id).first()
    if not t:
        raise NotFoundError("考试任务", task_id)
    if principal.role == "teacher" and principal.teacher_id != t.creator_id:
        raise ForbiddenError("仅可编辑自己创建的任务")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return _to_task_out(db, t)


@router.delete("/{task_id}")
def delete_task(task_id: int, _: Principal = Depends(require_permission("exam", "delete")), db: Session = Depends(get_db)):
    """真正删除任务并级联清理全部下游关联数据，单事务提交。"""
    t = db.query(models.ExamTask).filter(models.ExamTask.id == task_id).first()
    if not t:
        raise NotFoundError("考试任务", task_id)
    # 先收集本任务的答题卡 id，作为逐题评分删除依据
    sheet_ids = [
        r[0] for r in db.query(models.AnswerSheet.id).filter(models.AnswerSheet.task_id == task_id).all()
    ]
    # 1) 逐题评分（经 answer_sheet_id 关联）
    if sheet_ids:
        db.query(models.QuestionScore).filter(models.QuestionScore.answer_sheet_id.in_(sheet_ids)).delete(
            synchronize_session=False
        )
    # 2) 答题卡
    db.query(models.AnswerSheet).filter(models.AnswerSheet.task_id == task_id).delete(
        synchronize_session=False
    )
    # 3) 任务分配（学生）
    db.query(models.TaskAssignment).filter(models.TaskAssignment.task_id == task_id).delete(
        synchronize_session=False
    )
    # 4) 任务统计（task_id 唯一关联，避免孤儿数据）
    db.query(models.TaskStatistic).filter(models.TaskStatistic.task_id == task_id).delete(
        synchronize_session=False
    )
    # 5) 任务本身
    db.delete(t)
    db.commit()
    logger.info("exam_task_deleted", extra={"id": task_id})
    return {"code": 0, "message": "deleted", "data": None}


@router.post("/{task_id}/assign", response_model=ExamTaskOut)
def assign_students(task_id: int, student_ids: List[int], principal: Principal = Depends(require_permission("exam", "edit")), db: Session = Depends(get_db)):
    t = db.query(models.ExamTask).filter(models.ExamTask.id == task_id).first()
    if not t:
        raise NotFoundError("考试任务", task_id)
    if principal.role == "teacher" and principal.teacher_id != t.creator_id:
        raise ForbiddenError("仅可给自己任务分配学生")
    _assign(db, task_id, student_ids)
    return _to_task_out(db, t)


@router.get("/{task_id}/assignments", response_model=List[TaskAssignmentOut])
def list_assignments(task_id: int, principal: Principal = Depends(require_auth), db: Session = Depends(get_db)):
    t = db.query(models.ExamTask).filter(models.ExamTask.id == task_id).first()
    if not t:
        raise NotFoundError("考试任务", task_id)
    if principal.role == "teacher" and principal.teacher_id != t.creator_id:
        raise ForbiddenError("无权访问")
    rows = db.query(models.TaskAssignment).filter(models.TaskAssignment.task_id == task_id).all()
    out = []
    for r in rows:
        o = TaskAssignmentOut.model_validate(r)
        stu = db.query(models.Student).filter(models.Student.id == r.student_id).first()
        o.student_name = stu.name if stu else None
        o.student_code = stu.student_code if stu else None
        out.append(o)
    return out


@router.post("/{task_id}/answer-sheets", response_model=AnswerSheetOut, status_code=201)
def upload_answer_sheet(task_id: int, body: AnswerSheetCreate, principal: Principal = Depends(require_permission("exam", "edit")), db: Session = Depends(get_db)):
    t = db.query(models.ExamTask).filter(models.ExamTask.id == task_id).first()
    if not t:
        raise NotFoundError("考试任务", task_id)
    _ensure_task_owner(db, t, principal)
    stu = db.query(models.Student).filter(models.Student.id == body.student_id).first()
    if not stu:
        raise NotFoundError("学生", body.student_id)
    # 重复上传防护：同一学生同任务的旧有效卡置为 superseded，列表与统计只认 active
    db.query(models.AnswerSheet).filter(
        models.AnswerSheet.task_id == task_id,
        models.AnswerSheet.student_id == body.student_id,
        models.AnswerSheet.record_status == "active",
    ).update({"record_status": "superseded"}, synchronize_session=False)
    sheet = models.AnswerSheet(
        task_id=task_id,
        student_id=body.student_id,
        image_urls=body.image_urls,
        upload_type=body.upload_type,
        upload_device=body.upload_device,
        ai_status="pending",
    )
    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    # 识别答案随上传入库 + 客观题服务端判分（不再依赖前端内存数据）
    has_ungraded = _persist_recognized_answers(db, sheet, body.answers or [])
    sheet.ai_status = "processing" if has_ungraded else "completed"
    sheet.ai_started_at = sheet.ai_started_at or datetime.datetime.now(datetime.timezone.utc)
    sheet.ai_completed_at = datetime.datetime.now(datetime.timezone.utc)
    # 更新分配状态
    assign = (
        db.query(models.TaskAssignment)
        .filter(models.TaskAssignment.task_id == task_id, models.TaskAssignment.student_id == body.student_id)
        .first()
    )
    if assign:
        assign.status = "uploaded"
    # 任务状态推进：草稿/待考 → 考试回收中
    if t.status in ("draft", "pending"):
        t.status = "in_exam"
    db.commit()
    logger.info("answer_sheet_uploaded", extra={"id": sheet.id, "task": task_id})
    return AnswerSheetOut.model_validate(sheet)


def _sheet_out(db: Session, r: models.AnswerSheet) -> AnswerSheetOut:
    """组装答题卡输出：补学生编码/班级，并实时聚合每题评分得到总分。"""
    o = AnswerSheetOut.model_validate(r)
    stu = db.query(models.Student).filter(models.Student.id == r.student_id).first()
    if stu:
        o.student_name = stu.name
        o.student_code = stu.student_code
        cls = db.query(models.Class).filter(models.Class.id == stu.class_id).first()
        o.class_name = cls.name if cls else None
    scores = db.query(models.QuestionScore).filter(models.QuestionScore.answer_sheet_id == r.id).all()
    if scores:
        o.ai_total_score = round(sum(s.ai_score or 0 for s in scores), 1)
        o.teacher_total_score = round(sum(s.teacher_score or 0 for s in scores if s.teacher_score is not None), 1)
        o.final_score = round(sum(s.final_score if s.final_score is not None else (s.ai_score or 0) for s in scores), 1)
        o.question_count = len(scores)
    return o


@router.get("/{task_id}/answer-sheets", response_model=List[AnswerSheetOut])
def list_answer_sheets(task_id: int, principal: Principal = Depends(require_auth), db: Session = Depends(get_db)):
    t = db.query(models.ExamTask).filter(models.ExamTask.id == task_id).first()
    if not t:
        raise NotFoundError("考试任务", task_id)
    if principal.role == "teacher" and principal.teacher_id != t.creator_id:
        raise ForbiddenError("无权访问")
    rows = (
        db.query(models.AnswerSheet)
        .filter(models.AnswerSheet.task_id == task_id, models.AnswerSheet.record_status == "active")
        .all()
    )
    return [_sheet_out(db, r) for r in rows]


@router.post("/answer-sheets/{sheet_id}/score")
def score_answer_sheet(sheet_id: int, principal: Principal = Depends(require_permission("ai", "add")), db: Session = Depends(get_db)):
    """重新判分（确定性，替代原满分桩）。

    - 客观题按已入库的学生答案与标准答案归一化比对，更新 ai_score/final_score；
    - upsert 语义：教师已接管的行（teacher_modified/teacher_confirmed）保留人工结果；
    - 主观题(essay)不自动判分，保持待教师评分；
    - 无学生答案时返回明确错误，不再生成满分假数据。
    """
    sheet = db.query(models.AnswerSheet).filter(models.AnswerSheet.id == sheet_id).first()
    if not sheet:
        raise NotFoundError("答题卡", sheet_id)
    task = db.query(models.ExamTask).filter(models.ExamTask.id == sheet.task_id).first()
    if not task:
        raise NotFoundError("考试任务", sheet.task_id)
    _ensure_task_owner(db, task, principal)
    rows = db.query(models.QuestionScore).filter(models.QuestionScore.answer_sheet_id == sheet_id).all()
    if not rows:
        raise ValidationError("该答题卡没有学生答案数据，请先上传含识别结果的答题卡")
    pqs = {
        pq.id: pq
        for pq in db.query(models.PaperQuestion).filter(models.PaperQuestion.paper_id == task.paper_id).all()
    }
    qtype_cache: dict = {}
    for qs in rows:
        pq = pqs.get(qs.paper_question_id)
        if not pq:
            continue
        if qs.paper_question_id not in qtype_cache:
            q = (
                db.query(models.Question).filter(models.Question.id == pq.question_id).first()
                if pq.question_id
                else None
            )
            qtype_cache[qs.paper_question_id] = q.ques_type if q else "essay"
        if qtype_cache[qs.paper_question_id] == "essay":
            continue  # 主观题不动，等教师
        if qs.score_status in ("teacher_modified", "teacher_confirmed") and qs.teacher_score is not None:
            continue  # 教师已接管，保留人工评分
        ok = _grade_objective(qtype_cache[qs.paper_question_id], qs.student_answer, qs.correct_answer)
        if ok is None:
            continue
        qs.ai_score = float(pq.score or 0) if ok else 0.0
        qs.ai_max_score = pq.score or 0
        qs.ai_confidence = 1.0
        qs.ai_explanation = "客观题自动判分（重新评分）"
        qs.final_score = qs.ai_score
        qs.score_status = "ai_scored"
    has_ungraded = any(qs.final_score is None for qs in rows)
    sheet.ai_status = "processing" if has_ungraded else "completed"
    sheet.ai_completed_at = datetime.datetime.now(datetime.timezone.utc)
    if task.status in ("draft", "pending", "in_exam"):
        task.status = "scoring"
    db.commit()
    return {"code": 0, "message": "rescored", "data": {"answer_sheet_id": sheet_id}}


@router.get("/answer-sheets/{sheet_id}/scores", response_model=List[QuestionScoreOut])
def list_scores(sheet_id: int, principal: Principal = Depends(require_auth), db: Session = Depends(get_db)):
    sheet = db.query(models.AnswerSheet).filter(models.AnswerSheet.id == sheet_id).first()
    if not sheet:
        raise NotFoundError("答题卡", sheet_id)
    task = db.query(models.ExamTask).filter(models.ExamTask.id == sheet.task_id).first()
    if not task:
        raise NotFoundError("考试任务", sheet.task_id)
    _ensure_task_owner(db, task, principal)
    rows = db.query(models.QuestionScore).filter(models.QuestionScore.answer_sheet_id == sheet_id).all()
    return [QuestionScoreOut.model_validate(r) for r in rows]


@router.patch("/question-scores/{qid}", response_model=QuestionScoreOut)
def adjust_score(qid: int, body: QuestionScoreUpdate, principal: Principal = Depends(require_permission("ai", "edit")), db: Session = Depends(get_db)):
    qs = db.query(models.QuestionScore).filter(models.QuestionScore.id == qid).first()
    if not qs:
        raise NotFoundError("评分", qid)
    task = db.query(models.ExamTask).filter(models.ExamTask.id == qs.task_id).first()
    if not task:
        raise NotFoundError("考试任务", qs.task_id)
    _ensure_task_owner(db, task, principal)
    if body.teacher_score is not None:
        if body.teacher_score < 0 or (qs.ai_max_score and body.teacher_score > qs.ai_max_score):
            raise ValidationError(f"教师评分需在 0 ~ {qs.ai_max_score or '满分'} 之间")
        qs.teacher_score = body.teacher_score
        qs.final_score = body.teacher_score
        qs.score_status = "teacher_modified" if body.teacher_score != qs.ai_score else "teacher_confirmed"
    if body.teacher_comment is not None:
        qs.ai_explanation = (qs.ai_explanation or "") + f"\n教师批注: {body.teacher_comment}"
    db.commit()
    db.refresh(qs)
    return QuestionScoreOut.model_validate(qs)


@router.get("/{task_id}/dashboard", response_model=ExamDashboardOut)
def task_dashboard(task_id: int, principal: Principal = Depends(require_auth), db: Session = Depends(get_db)):
    t = db.query(models.ExamTask).filter(models.ExamTask.id == task_id).first()
    if not t:
        raise NotFoundError("考试任务", task_id)
    if principal.role == "teacher" and principal.teacher_id != t.creator_id:
        raise ForbiddenError("无权访问")
    return _compute_task_dashboard(db, t)


def _compute_task_dashboard(db: Session, t: models.ExamTask) -> ExamDashboardOut:
    """实时聚合任务看板统计（不依赖统计表，直接从答题卡 + 每题评分计算）。"""
    out = ExamDashboardOut(task_id=t.id)

    # 应考学生（任务分配）与答题卡
    assigned = (
        db.query(models.TaskAssignment)
        .filter(models.TaskAssignment.task_id == t.id)
        .all()
    )
    sheets = (
        db.query(models.AnswerSheet)
        .filter(models.AnswerSheet.task_id == t.id, models.AnswerSheet.record_status == "active")
        .all()
    )
    out.student_count = len(assigned)
    out.upload_count = len(sheets)
    if out.student_count:
        out.upload_rate = round(len(sheets) / out.student_count * 100, 1)

    # 试卷题目快照（题型/难度/知识点/满分）
    paper = db.query(models.Paper).filter(models.Paper.id == t.paper_id).first()
    pq_rows = (
        db.query(models.PaperQuestion)
        .filter(models.PaperQuestion.paper_id == t.paper_id)
        .order_by(models.PaperQuestion.sort_order)
        .all()
    )
    out.question_count = len(pq_rows)
    pq_map = {}  # paper_question_id -> {type, difficulty, knowledge, max_score}
    qid_to_pq = {}  # question_id -> paper_question
    for pq in pq_rows:
        q = db.query(models.Question).filter(models.Question.id == pq.question_id).first() if pq.question_id else None
        pq_map[pq.id] = {
            "type": q.ques_type if q else None,
            "difficulty": q.difficulty if q else None,
            "knowledge": (q.knowledge_ids or []) if q else [],
            "max_score": pq.score or 0,
            "number": pq.sort_order,
        }
        if pq.question_id:
            qid_to_pq[pq.question_id] = pq

    # 每题评分（仅有效答题卡；排除被替换的 superseded 旧卡，防止双卡重复累加）
    active_sheet_ids = [s.id for s in sheets]
    scores = (
        db.query(models.QuestionScore)
        .filter(
            models.QuestionScore.task_id == t.id,
            models.QuestionScore.answer_sheet_id.in_(active_sheet_ids),
        )
        .all()
    ) if active_sheet_ids else []
    if not scores:
        return out

    # 每生总分
    student_scores = {}  # student_id -> total final_score
    for s in scores:
        final = s.final_score if s.final_score is not None else (s.ai_score or 0)
        student_scores[s.student_id] = student_scores.get(s.student_id, 0) + final
    values = sorted(student_scores.values())
    n = len(values)
    if n:
        out.avg_score = round(sum(values) / n, 1)
        out.max_score = round(values[-1], 1)
        out.min_score = round(values[0], 1)
        full = (sum(pq_map.get(s.paper_question_id, {}).get("max_score", 0) for s in scores) / len(scores)) if scores else 100
        # 及格/优秀率：按满分比例（>=60% 及格，>=85% 优秀），满分从试卷 total_score 兜底
        total_full = paper.total_score if paper and paper.total_score else (out.max_score or 100)
        pass_thr = total_full * 0.6
        exc_thr = total_full * 0.85
        out.pass_rate = round(sum(1 for v in values if v >= pass_thr) / n * 100, 1)
        out.excellent_rate = round(sum(1 for v in values if v >= exc_thr) / n * 100, 1)
        # 分数段分布
        bins = [("90+", lambda v: v >= total_full * 0.9),
                ("80-89", lambda v: total_full * 0.8 <= v < total_full * 0.9),
                ("70-79", lambda v: total_full * 0.7 <= v < total_full * 0.8),
                ("60-69", lambda v: total_full * 0.6 <= v < total_full * 0.7),
                ("<60", lambda v: v < total_full * 0.6)]
        out.score_distribution = [{"label": label, "count": sum(1 for v in values if fn(v))} for label, fn in bins]

    # 逐题正确率（按题目聚合，正确 = final/ai 得分 >= 满分*0.6 视为答对该题）
    by_q = {}
    for s in scores:
        pq = pq_map.get(s.paper_question_id)
        if not pq:
            continue
        num = pq["number"]
        if num not in by_q:
            by_q[num] = {"total": 0, "correct": 0, "sum": 0.0, "max": pq["max_score"]}
        by_q[num]["total"] += 1
        final = s.final_score if s.final_score is not None else (s.ai_score or 0)
        by_q[num]["sum"] += final
        if pq["max_score"] and final >= pq["max_score"] * 0.6:
            by_q[num]["correct"] += 1
    out.question_correct_rate = [
        {"question_number": num, "correct_rate": round(d["correct"] / d["total"] * 100, 1),
         "score_rate": round(d["sum"] / d["total"] / d["max"] * 100, 1) if d["max"] else 0}
        for num, d in sorted(by_q.items())
    ]

    # 题型/难度得分率
    type_agg, diff_agg, know_agg = {}, {}, {}
    for s in scores:
        pq = pq_map.get(s.paper_question_id)
        if not pq:
            continue
        final = s.final_score if s.final_score is not None else (s.ai_score or 0)
        mx = pq["max_score"]
        rate = (final / mx) if mx else 0
        tt = pq["type"]
        if tt:
            a = type_agg.setdefault(tt, {"sum": 0.0, "n": 0, "max": 0})
            a["sum"] += final; a["n"] += 1; a["max"] += mx
        d = pq["difficulty"]
        if d:
            a = diff_agg.setdefault(d, {"sum": 0.0, "n": 0, "max": 0})
            a["sum"] += final; a["n"] += 1; a["max"] += mx
        for kid in pq["knowledge"]:
            a = know_agg.setdefault(kid, {"sum": 0.0, "n": 0, "max": 0})
            a["sum"] += final; a["n"] += 1; a["max"] += mx
    out.type_performance = [{"type": k, "score_rate": round(v["sum"] / v["max"] * 100, 1) if v["max"] else 0}
                            for k, v in sorted(type_agg.items())]
    out.difficulty_performance = [{"difficulty": k, "score_rate": round(v["sum"] / v["max"] * 100, 1) if v["max"] else 0}
                                  for k, v in sorted(diff_agg.items())]
    # 知识点名解析
    out.knowledge_performance = []
    for kid, v in sorted(know_agg.items(), key=lambda x: -(x[1]["sum"] / x[1]["max"] if x[1]["max"] else 0)):
        name = kid
        cat = db.query(models.Category).filter(models.Category.id == kid).first() if isinstance(kid, int) else None
        if cat:
            name = cat.name
        out.knowledge_performance.append({"knowledge": name, "score_rate": round(v["sum"] / v["max"] * 100, 1) if v["max"] else 0})

    # 低置信度题目数
    out.low_confidence_count = sum(1 for s in scores if s.ai_confidence is not None and s.ai_confidence < 0.7)
    return out


# ---------------------------------------------------------------------------
# 答题卡打印（任务级：批量 / 单人补打）+ 任务试卷模板继承下载
# ---------------------------------------------------------------------------
def _category_name(db: Session, cat_id) -> Optional[str]:
    if not cat_id:
        return None
    cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
    return cat.name if cat else None


def _paper_dict(db: Session, paper: models.Paper) -> dict:
    """渲染器需要的试卷纯数据（含学科名）。"""
    return {
        "code": paper.paper_code,
        "name": paper.name,
        "subject": _category_name(db, paper.subject_id) or "",
    }


def _task_paper_questions(db: Session, paper_id: int) -> List[dict]:
    """按组卷快照（PaperQuestion）顺序返回题目数据，type 取题库题型，score 取快照分值。"""
    pqs = (
        db.query(models.PaperQuestion)
        .filter(models.PaperQuestion.paper_id == paper_id)
        .order_by(models.PaperQuestion.sort_order)
        .all()
    )
    out: List[dict] = []
    for pq in pqs:
        q = (
            db.query(models.Question).filter(models.Question.id == pq.question_id).first()
            if pq.question_id
            else None
        )
        out.append(
            {
                "type": q.ques_type if q else "essay",
                "options": q.options if q else [],
                "score": pq.score or (q.score if q else 0),
                "stem": q.stem if q else "",
                "answer": q.answer if q else "",
            }
        )
    return out


def _task_students(db: Session, task: models.ExamTask) -> List[dict]:
    """照抄前端 downloadTaskAnswerSheetsPdf 取学生逻辑（4469-4479 行）：
    优先按任务分配的学生（student_ids），否则按任务关联班级（class_ids）取全班学生，最后去重。
    """
    assigned = (
        db.query(models.TaskAssignment.student_id)
        .filter(models.TaskAssignment.task_id == task.id)
        .all()
    )
    stu_ids: List[int] = []
    if assigned:
        stu_ids = [r[0] for r in assigned]
    else:
        # 班级来源：任务分配表中聚合的 distinct class_id（与 _to_task_out 口径一致）
        cids = (
            db.query(models.TaskAssignment.class_id)
            .filter(models.TaskAssignment.task_id == task.id, models.TaskAssignment.class_id.isnot(None))
            .distinct()
            .all()
        )
        if cids:
            class_ids = [c[0] for c in cids]
            rows = (
                db.query(models.Student.id)
                .filter(models.Student.class_id.in_(class_ids))
                .all()
            )
            stu_ids = [r[0] for r in rows]
    out: List[dict] = []
    seen = set()
    for sid in stu_ids:
        if sid in seen:
            continue
        seen.add(sid)
        stu = db.query(models.Student).filter(models.Student.id == sid).first()
        if not stu:
            continue
        class_name = ""
        if stu.class_id:
            cls = db.query(models.Class).filter(models.Class.id == stu.class_id).first()
            class_name = cls.name if cls else ""
        out.append(
            {
                "id": stu.id,
                "code": stu.student_code,
                "name": stu.name,
                "className": class_name,
            }
        )
    return out


@router.get("/{task_id}/answer-sheets/print", response_class=HTMLResponse)
def print_answer_sheets(
    task_id: int,
    student_id: Optional[int] = None,
    format: Optional[str] = Query(None, description="预留：format=pdf（当前统一返回 HTML，前端 window.print 另存 PDF）"),
    principal: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """任务答题卡打印：无 student_id 批量全部学生（每生一页）；有 student_id 单人补打。"""
    t = db.query(models.ExamTask).filter(models.ExamTask.id == task_id).first()
    if not t:
        raise NotFoundError("考试任务", task_id)
    if principal.role == "teacher" and principal.teacher_id != t.creator_id:
        raise ForbiddenError("仅可访问自己创建的任务")
    paper = db.query(models.Paper).filter(models.Paper.id == t.paper_id).first()
    if not paper:
        raise NotFoundError("试卷", t.paper_id)
    questions = _task_paper_questions(db, t.paper_id)
    if not questions:
        raise ValidationError("该试卷无题目，无法生成答题卡")

    paper_dict = _paper_dict(db, paper)
    task_dict = {"code": t.task_code, "name": t.name}
    students = _task_students(db, t)

    if student_id is not None:
        stu = next((s for s in students if s["id"] == student_id), None)
        if not stu:
            raise ValidationError("该学生不在本任务中")
        html = render_multi_sheet_html(task_dict, [stu], paper_dict, questions)
    else:
        if not students:
            raise ValidationError("该任务未分配学生，无法生成答题卡")
        html = render_multi_sheet_html(task_dict, students, paper_dict, questions)
    logger.info("exam_task_answer_sheets_printed", extra={"task": task_id, "student_id": student_id})
    return HTMLResponse(content=html)


@router.get("/{task_id}/paper/template")
def task_paper_template(
    task_id: int,
    principal: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """任务试卷 Word 模板下载（继承试卷模板：复用 paper.py 的模板文件，含用户自定义版；
    无模板自动生成 docx；下载文件名 = 任务名+试卷名.docx）。"""
    t = db.query(models.ExamTask).filter(models.ExamTask.id == task_id).first()
    if not t:
        raise NotFoundError("考试任务", task_id)
    if principal.role == "teacher" and principal.teacher_id != t.creator_id:
        raise ForbiddenError("仅可访问自己创建的任务")
    paper = db.query(models.Paper).filter(models.Paper.id == t.paper_id).first()
    if not paper:
        raise NotFoundError("试卷", t.paper_id)
    # 继承试卷模板：A1 在 paper.py 已实现懒生成 + 用户自定义版优先，这里直接调用
    row = _ensure_paper_template(db, paper)
    filename = f"{t.name}-{paper.name}.docx"
    return _download_response(row.file_path, filename)
