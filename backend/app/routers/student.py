"""学生接口。

端点：
  GET    /api/v1/students             列表（分页；教师限关联班级）
  GET    /api/v1/students/{id}        详情
  POST   /api/v1/students             新建（自动生成 student_code A01-Z99，不可手填）
  PUT    /api/v1/students/{id}        更新（student_code 不变）
  DELETE /api/v1/students/{id}        删除（物理删除，级联清除考试数据）
  GET    /api/v1/students/{id}/dashboard  全景看板

学生ID规则 §8.1：1 字母(A-Z) + 2 位数字(01-99)；序列 A01→A99→B01→…→Z99；容量 2574；
系统自动分配，物理删除后编号可回收复用，超限报错。
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.errors import NotFoundError, ValidationError, ConflictError, ForbiddenError
from ..core.logging import logger
from ..core.permissions import teacher_visible_class_ids
from ..core.security import Principal, require_auth, require_permission
from ..schemas.student import (
    StudentCreate,
    StudentOut,
    StudentUpdate,
    PaginatedStudent,
    StudentDashboard,
    EvaluationCreate,
)

router = APIRouter(prefix="/api/v1/students", tags=["student"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_student_code(db: Session) -> str:
    used = {r.student_code for r in db.query(models.Student).all() if r.student_code}
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        for num in range(1, 100):
            code = f"{letter}{num:02d}"
            if code not in used:
                return code
    raise ConflictError("学生编号已用完(A01-Z99)")


def _to_out(db: Session, s: models.Student) -> StudentOut:
    out = StudentOut.model_validate(s)
    if s.class_id:
        c = db.query(models.Class).filter(models.Class.id == s.class_id).first()
        out.class_name = c.name if c else None
    return out


@router.get("", response_model=PaginatedStudent)
def list_students(
    class_id: Optional[int] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    principal: Principal = Depends(require_permission("student","view")),
    db: Session = Depends(get_db),
):
    query = db.query(models.Student)
    visible = teacher_visible_class_ids(db, principal)
    if visible is not None:
        query = query.filter(models.Student.class_id.in_(visible))
    if class_id:
        query = query.filter(models.Student.class_id == class_id)
    if q:
        query = query.filter(models.Student.name.ilike(f"%{q}%"))
    total = query.count()
    rows = (
        query.order_by(desc(models.Student.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedStudent(
        items=[_to_out(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, principal: Principal = Depends(require_permission("student","view")), db: Session = Depends(get_db)):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise NotFoundError("学生", student_id)
    visible = teacher_visible_class_ids(db, principal)
    if visible is not None and s.class_id not in visible:
        raise ForbiddenError("无权访问该学生")
    return _to_out(db, s)


@router.post("", response_model=StudentOut, status_code=201)
def create_student(body: StudentCreate, principal: Principal = Depends(require_permission("student", "add")), db: Session = Depends(get_db)):
    cls = db.query(models.Class).filter(models.Class.id == body.class_id).first()
    if not cls:
        raise NotFoundError("班级", body.class_id)
    visible = teacher_visible_class_ids(db, principal)
    if visible is not None and body.class_id not in visible:
        raise ForbiddenError("无权在该班级新建学生")
    code = generate_student_code(db)
    s = models.Student(student_code=code, **body.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    logger.info("student_created", extra={"id": s.id, "code": code})
    return _to_out(db, s)


@router.put("/{student_id}", response_model=StudentOut)
def update_student(student_id: int, body: StudentUpdate, principal: Principal = Depends(require_permission("student", "edit")), db: Session = Depends(get_db)):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise NotFoundError("学生", student_id)
    visible = teacher_visible_class_ids(db, principal)
    if visible is not None and s.class_id not in visible:
        raise ForbiddenError("无权编辑该学生")
    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "student_code":
            continue  # 不可改
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return _to_out(db, s)


@router.delete("/{student_id}")
def delete_student(student_id: int, principal: Principal = Depends(require_permission("student", "delete")), db: Session = Depends(get_db)):
    """物理删除学生并级联清除全部下游数据（单事务）。

    级联链（均为不可空外键，只能级联删）：
      question_scores（经答题卡）→ answer_sheets → task_assignments → student_statistics → students
    """
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise NotFoundError("学生", student_id)
    visible = teacher_visible_class_ids(db, principal)
    if visible is not None and s.class_id not in visible:
        raise ForbiddenError("无权删除该学生")
    # 1) 逐题评分：先删经答题卡关联的，再删直接 student_id 关联的（覆盖边界情况）
    sheet_ids = [
        r[0] for r in db.query(models.AnswerSheet.id).filter(models.AnswerSheet.student_id == student_id).all()
    ]
    if sheet_ids:
        db.query(models.QuestionScore).filter(models.QuestionScore.answer_sheet_id.in_(sheet_ids)).delete(
            synchronize_session=False
        )
    db.query(models.QuestionScore).filter(models.QuestionScore.student_id == student_id).delete(
        synchronize_session=False
    )
    # 2) 答题卡
    db.query(models.AnswerSheet).filter(models.AnswerSheet.student_id == student_id).delete(
        synchronize_session=False
    )
    # 3) 任务分配
    db.query(models.TaskAssignment).filter(models.TaskAssignment.student_id == student_id).delete(
        synchronize_session=False
    )
    # 4) 学生统计
    db.query(models.StudentStatistic).filter(models.StudentStatistic.student_id == student_id).delete(
        synchronize_session=False
    )
    # 5) 学生本体
    db.delete(s)
    db.commit()
    logger.info("student_deleted", extra={"id": student_id})
    return {"code": 0, "message": "deleted", "data": None}


@router.post("/{student_id}/evaluations")
def add_evaluation(student_id: int, body: EvaluationCreate, principal: Principal = Depends(require_permission("student", "edit")), db: Session = Depends(get_db)):
    """添加/更新一条考后教师评价（同 task_code 去重覆盖），写入 recent_evaluations。"""
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise NotFoundError("学生", student_id)
    visible = teacher_visible_class_ids(db, principal)
    if visible is not None and s.class_id not in visible:
        raise ForbiddenError("无权评价该学生")
    import uuid
    evals = list(s.recent_evaluations or [])
    rec = body.model_dump()
    rec["id"] = uuid.uuid4().hex[:10]
    # 同 task_code 去重覆盖
    idx = next((i for i, e in enumerate(evals) if body.task_code and e.get("task_code") == body.task_code), None)
    if idx is not None:
        rec["id"] = evals[idx].get("id") or rec["id"]
        evals[idx] = rec
    else:
        evals.append(rec)
    s.recent_evaluations = evals
    db.commit()
    logger.info("student_evaluation_added", extra={"student_id": student_id, "task_code": body.task_code})
    return {"code": 0, "message": "ok", "data": rec}


@router.get("/{student_id}/dashboard", response_model=StudentDashboard)
def dashboard(student_id: int, principal: Principal = Depends(require_permission("student","view")), db: Session = Depends(get_db)):
    s = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not s:
        raise NotFoundError("学生", student_id)
    visible = teacher_visible_class_ids(db, principal)
    if visible is not None and s.class_id not in visible:
        raise ForbiddenError("无权访问该学生看板")
    return _compute_student_dashboard(db, s)


def _compute_student_dashboard(db: Session, s: models.Student) -> StudentDashboard:
    """实时聚合学生看板统计（从答题卡 + 每题评分计算）。"""
    out = StudentDashboard(student_id=s.id)

    # 该学生所有答题卡 + 每题评分
    sheets = (
        db.query(models.AnswerSheet)
        .filter(models.AnswerSheet.student_id == s.id)
        .order_by(models.AnswerSheet.created_at)
        .all()
    )
    out.exam_count = len(sheets)
    if not sheets:
        return out

    scores = (
        db.query(models.QuestionScore)
        .filter(models.QuestionScore.student_id == s.id)
        .all()
    )
    # 每张答题卡总分
    sheet_scores = []
    for sheet in sheets:
        ss = [x for x in scores if x.answer_sheet_id == sheet.id]
        total = sum(x.final_score if x.final_score is not None else (x.ai_score or 0) for x in ss)
        sheet_scores.append({"task_id": sheet.task_id, "total": total, "date": sheet.created_at})
    values = sorted(x["total"] for x in sheet_scores)
    n = len(values)
    out.avg_score = round(sum(values) / n, 1)
    out.max_score = round(values[-1], 1)
    out.min_score = round(values[0], 1)
    out.score_trend = [{"label": (x["date"].strftime("%m/%d") if x["date"] else ""), "score": round(x["total"], 1)}
                       for x in sheet_scores]

    # 参与率：已参与任务数 / 班级应考任务数（用答题卡近似，班级任务数）
    cls_tasks = (
        db.query(models.ExamTask.id)
        .join(models.TaskAssignment, models.TaskAssignment.task_id == models.ExamTask.id)
        .filter(models.TaskAssignment.student_id == s.id)
        .distinct()
        .count()
    )
    out.expected_count = cls_tasks
    out.participation_rate = round(n / cls_tasks * 100, 1) if cls_tasks else (100.0 if n else None)

    # 班级排名：最后一次考试在班级内排名
    last = sheet_scores[-1]
    classmates = (
        db.query(models.QuestionScore)
        .filter(models.QuestionScore.task_id == last["task_id"], models.QuestionScore.student_id != s.id)
        .all()
    )
    ctot = {}
    for x in classmates:
        ctot[x.student_id] = ctot.get(x.student_id, 0) + (x.final_score if x.final_score is not None else (x.ai_score or 0))
    better = sum(1 for v in ctot.values() if v > last["total"])
    out.class_rank = better + 1

    # 题型正确率 / 知识点掌握度
    type_agg, know_agg = {}, {}
    for x in scores:
        pq = db.query(models.PaperQuestion).filter(models.PaperQuestion.id == x.paper_question_id).first()
        q = db.query(models.Question).filter(models.Question.id == pq.question_id).first() if (pq and pq.question_id) else None
        if not pq:
            continue
        final = x.final_score if x.final_score is not None else (x.ai_score or 0)
        mx = pq.score or 0
        rate = (final / mx) if mx else 0
        tt = q.ques_type if q else None
        if tt:
            a = type_agg.setdefault(tt, {"sum": 0.0, "max": 0})
            a["sum"] += final; a["max"] += mx
        for kid in ((q.knowledge_ids or []) if q else []):
            a = know_agg.setdefault(kid, {"sum": 0.0, "max": 0})
            a["sum"] += final; a["max"] += mx
    out.type_accuracy = [{"type": k, "accuracy": round(v["sum"] / v["max"] * 100, 1) if v["max"] else 0}
                         for k, v in sorted(type_agg.items())]
    know_list = []
    for kid, v in know_agg.items():
        name = kid
        cat = db.query(models.Category).filter(models.Category.id == kid).first() if isinstance(kid, int) else None
        if cat:
            name = cat.name
        rate = round(v["sum"] / v["max"] * 100, 1) if v["max"] else 0
        know_list.append({"knowledge": name, "mastery": rate})
    know_list.sort(key=lambda x: x["mastery"])
    out.knowledge_mastery = know_list
    out.weak_knowledge = [x for x in know_list if x["mastery"] < 60][:5]
    out.strong_knowledge = [x for x in know_list if x["mastery"] >= 80][:5]
    out.improvement_status = "improving" if n >= 2 and values[-1] >= values[-2] else "stable"
    return out
