"""班级接口。

端点：
  GET    /api/v1/classes             列表（分页；教师限关联班级）
  GET    /api/v1/classes/{id}        详情
  POST   /api/v1/classes             新建（自动生成 class_code A/B/C+01-99）
  PUT    /api/v1/classes/{id}        更新
  DELETE /api/v1/classes/{id}        删除（物理删除；有学生时拒绝）
  GET    /api/v1/classes/{id}/dashboard  全景看板

班级ID规则 §9.1：学段字母前缀 + 2 位流水（A 小学 / B 初中 / C 高中，01-99）。
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.errors import NotFoundError, ValidationError, ConflictError, ForbiddenError
from ..core.logging import logger
from ..core.security import Principal, require_auth, require_permission
from ..schemas.class_schema import (
    ClassCreate,
    ClassOut,
    ClassUpdate,
    PaginatedClass,
    ClassDashboard,
)
from ..models.class_model import STAGE_MAP

router = APIRouter(prefix="/api/v1/classes", tags=["class"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def teacher_visible_class_ids(db: Session, principal: Principal) -> Optional[List[int]]:
    if principal.role == "admin":
        return None
    rows = db.query(models.TeacherClass).filter(models.TeacherClass.teacher_id == principal.teacher_id).all()
    return [r.class_id for r in rows]


def generate_class_code(db: Session, stage: str) -> str:
    prefix = STAGE_MAP[stage]
    rows = (
        db.query(models.Class)
        .filter(models.Class.class_code.like(f"{prefix}%"))
        .all()
    )
    max_seq = 0
    for r in rows:
        try:
            seq = int(r.class_code[1:])
            max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            continue
    if max_seq >= 99:
        raise ConflictError(f"{stage} 班级编号已用完(99)")
    return f"{prefix}{max_seq + 1:02d}"


def _to_out(db: Session, c: models.Class) -> ClassOut:
    stat = db.query(models.ClassStatistic).filter(models.ClassStatistic.class_id == c.id).first()
    out = ClassOut.model_validate(c)
    out.student_count = stat.student_count if stat else 0
    return out


@router.get("", response_model=PaginatedClass)
def list_classes(
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    principal: Principal = Depends(require_permission("class","view")),
    db: Session = Depends(get_db),
):
    query = db.query(models.Class)
    visible = teacher_visible_class_ids(db, principal)
    if visible is not None:
        query = query.filter(models.Class.id.in_(visible))
    if q:
        query = query.filter(models.Class.name.ilike(f"%{q}%"))
    total = query.count()
    rows = (
        query.order_by(desc(models.Class.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedClass(
        items=[_to_out(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{class_id}", response_model=ClassOut)
def get_class(class_id: int, principal: Principal = Depends(require_permission("class","view")), db: Session = Depends(get_db)):
    c = db.query(models.Class).filter(models.Class.id == class_id).first()
    if not c:
        raise NotFoundError("班级", class_id)
    visible = teacher_visible_class_ids(db, principal)
    if visible is not None and class_id not in visible:
        raise ForbiddenError("无权访问该班级")
    return _to_out(db, c)


@router.post("", response_model=ClassOut, status_code=201)
def create_class(body: ClassCreate, _: Principal = Depends(require_permission("class", "add")), db: Session = Depends(get_db)):
    code = generate_class_code(db, body.stage)
    c = models.Class(class_code=code, name=body.name, stage=body.stage, remark=body.remark, status="active")
    db.add(c)
    db.commit()
    db.refresh(c)
    logger.info("class_created", extra={"id": c.id, "code": code})
    return _to_out(db, c)


@router.put("/{class_id}", response_model=ClassOut)
def update_class(class_id: int, body: ClassUpdate, _: Principal = Depends(require_permission("class", "edit")), db: Session = Depends(get_db)):
    c = db.query(models.Class).filter(models.Class.id == class_id).first()
    if not c:
        raise NotFoundError("班级", class_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return _to_out(db, c)


@router.delete("/{class_id}")
def delete_class(class_id: int, _: Principal = Depends(require_permission("class", "delete")), db: Session = Depends(get_db)):
    """物理删除班级（单事务）。

    处理下游引用：
      1) 仍有学生属于该班级时拒绝（students.class_id 不可空，属数据完整性保护）；
      2) TeacherClass 教师-班级关联：级联删除；
      3) TaskAssignment.class_id 快照（可空）：置 NULL；
      4) ClassStatistic 班级统计：级联删除。
    """
    c = db.query(models.Class).filter(models.Class.id == class_id).first()
    if not c:
        raise NotFoundError("班级", class_id)
    stu_cnt = (
        db.query(models.Student)
        .filter(models.Student.class_id == class_id)
        .count()
    )
    if stu_cnt:
        raise ConflictError(f"该班级下仍有 {stu_cnt} 名学生，请先转移或删除学生")
    # 1) 教师-班级关联
    db.query(models.TeacherClass).filter(models.TeacherClass.class_id == class_id).delete(
        synchronize_session=False
    )
    # 2) 任务分配中的班级快照置空（可空字段，保留考试数据）
    db.query(models.TaskAssignment).filter(models.TaskAssignment.class_id == class_id).update(
        {models.TaskAssignment.class_id: None}, synchronize_session=False
    )
    # 3) 班级统计
    db.query(models.ClassStatistic).filter(models.ClassStatistic.class_id == class_id).delete(
        synchronize_session=False
    )
    # 4) 班级本体
    db.delete(c)
    db.commit()
    logger.info("class_deleted", extra={"id": class_id})
    return {"code": 0, "message": "deleted", "data": None}


@router.get("/{class_id}/dashboard", response_model=ClassDashboard)
def dashboard(class_id: int, principal: Principal = Depends(require_permission("class","view")), db: Session = Depends(get_db)):
    c = db.query(models.Class).filter(models.Class.id == class_id).first()
    if not c:
        raise NotFoundError("班级", class_id)
    visible = teacher_visible_class_ids(db, principal)
    if visible is not None and class_id not in visible:
        raise ForbiddenError("无权访问该班级看板")
    return _compute_class_dashboard(db, c)


def _compute_class_dashboard(db: Session, c: models.Class) -> ClassDashboard:
    """实时聚合班级看板统计（从学生 + 答题卡 + 每题评分计算）。"""
    out = ClassDashboard(class_id=c.id)
    students = db.query(models.Student).filter(models.Student.class_id == c.id, models.Student.status == "active").all()
    out.student_count = len(students)
    if not students:
        return out
    sids = [s.id for s in students]

    scores = db.query(models.QuestionScore).filter(models.QuestionScore.student_id.in_(sids)).all()
    if not scores:
        return out

    # 每生总分
    per_stu = {}
    for x in scores:
        per_stu[x.student_id] = per_stu.get(x.student_id, 0) + (x.final_score if x.final_score is not None else (x.ai_score or 0))
    values = sorted(per_stu.values())
    n = len(values)
    total_full = max(values) or 100
    out.avg_score = round(sum(values) / n, 1)
    pass_thr, exc_thr = total_full * 0.6, total_full * 0.85
    out.pass_rate = round(sum(1 for v in values if v >= pass_thr) / n * 100, 1)
    out.excellent_rate = round(sum(1 for v in values if v >= exc_thr) / n * 100, 1)
    bins = [("90+", lambda v: v >= total_full * 0.9), ("80-89", lambda v: total_full * 0.8 <= v < total_full * 0.9),
            ("70-79", lambda v: total_full * 0.7 <= v < total_full * 0.8), ("60-69", lambda v: total_full * 0.6 <= v < total_full * 0.7),
            ("<60", lambda v: v < total_full * 0.6)]
    out.score_distribution = [{"label": label, "count": sum(1 for v in values if fn(v))} for label, fn in bins]
    # 能力分组
    out.ability_groups = [
        {"group": "优秀", "count": sum(1 for v in values if v >= total_full * 0.85)},
        {"group": "良好", "count": sum(1 for v in values if total_full * 0.7 <= v < total_full * 0.85)},
        {"group": "及格", "count": sum(1 for v in values if total_full * 0.6 <= v < total_full * 0.7)},
        {"group": "待提升", "count": sum(1 for v in values if v < total_full * 0.6)},
    ]

    # 题型/难度得分率
    type_agg, diff_agg = {}, {}
    for x in scores:
        pq = db.query(models.PaperQuestion).filter(models.PaperQuestion.id == x.paper_question_id).first()
        q = db.query(models.Question).filter(models.Question.id == pq.question_id).first() if (pq and pq.question_id) else None
        if not pq:
            continue
        final = x.final_score if x.final_score is not None else (x.ai_score or 0)
        mx = pq.score or 0
        tt = q.ques_type if q else None
        if tt:
            a = type_agg.setdefault(tt, {"sum": 0.0, "max": 0}); a["sum"] += final; a["max"] += mx
        d = q.difficulty if q else None
        if d:
            a = diff_agg.setdefault(d, {"sum": 0.0, "max": 0}); a["sum"] += final; a["max"] += mx
    out.type_performance = [{"type": k, "score_rate": round(v["sum"] / v["max"] * 100, 1) if v["max"] else 0}
                            for k, v in sorted(type_agg.items())]
    out.difficulty_performance = [{"difficulty": k, "score_rate": round(v["sum"] / v["max"] * 100, 1) if v["max"] else 0}
                                  for k, v in sorted(diff_agg.items())]

    # 学生排行（按总分）
    stu_name = {s.id: s.name for s in students}
    stu_code = {s.id: s.student_code for s in students}
    ranked = sorted(per_stu.items(), key=lambda kv: -kv[1])
    out.top_students = [{"student_id": sid, "name": stu_name.get(sid), "code": stu_code.get(sid), "score": round(v, 1)}
                        for sid, v in ranked[:5]]
    out.bottom_students = [{"student_id": sid, "name": stu_name.get(sid), "code": stu_code.get(sid), "score": round(v, 1)}
                           for sid, v in ranked[-5:]][::-1]
    out.improvement_list = [{"name": stu_name.get(sid), "code": stu_code.get(sid), "score": round(v, 1)}
                            for sid, v in ranked[:3]]
    out.decline_list = [{"name": stu_name.get(sid), "code": stu_code.get(sid), "score": round(v, 1)}
                        for sid, v in ranked[-3:]][::-1]
    return out
