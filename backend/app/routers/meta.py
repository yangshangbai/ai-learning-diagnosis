"""基础数据枚举接口：对齐 Demo MOCK DATA 的 subjects/grades/questionTypes/difficulties。

数据来自 categories 表（由 seed.py 初始化）：
  - subjects      category_type='subject'
  - grades        category_type='grade'        extra.stage = primary/middle/high
  - questionTypes category_type='question_type' extra.short = 单选/多选/...
  - difficulties  category_type='difficulty'    code = 1..5

附加端点：
  GET /api/v1/meta/next-code?type=student|class|teacher  生成下一编号（best-effort）
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.errors import ValidationError
from ..core.security import Principal, require_auth

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
def get_meta(
    _: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    subjects = (
        db.query(models.Category)
        .filter(models.Category.category_type == "subject", models.Category.status == "active")
        .order_by(models.Category.sort_order, models.Category.id)
        .all()
    )
    grades = (
        db.query(models.Category)
        .filter(models.Category.category_type == "grade", models.Category.status == "active")
        .order_by(models.Category.sort_order, models.Category.id)
        .all()
    )
    qtypes = (
        db.query(models.Category)
        .filter(models.Category.category_type == "question_type", models.Category.status == "active")
        .order_by(models.Category.sort_order, models.Category.id)
        .all()
    )
    diffs = (
        db.query(models.Category)
        .filter(models.Category.category_type == "difficulty", models.Category.status == "active")
        .order_by(models.Category.sort_order, models.Category.id)
        .all()
    )

    extra = lambda r: r.extra or {}

    return {
        "subjects": [
            {"id": r.id, "code": r.code, "name": r.name} for r in subjects
        ],
        "grades": [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "stage": extra(r).get("stage"),
            }
            for r in grades
        ],
        "questionTypes": [
            {
                "code": r.code,
                "name": r.name,
                "short": extra(r).get("short", r.name),
            }
            for r in qtypes
        ],
        "difficulties": [
            {"level": int(r.code) if r.code and str(r.code).isdigit() else r.id, "name": r.name}
            for r in diffs
        ],
    }


def _next_student_code(db: Session) -> str:
    """A01-Z99：1 字母 + 2 位数字，序列递增，删除不回收。"""
    used = {r.student_code for r in db.query(models.Student).all() if r.student_code}
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        for num in range(1, 100):
            code = f"{letter}{num:02d}"
            if code not in used:
                return code
    raise ValidationError("学生编号已用完(A01-Z99)")


def _next_class_code(db: Session) -> str:
    """班级编号：A/B/C + 2 位数字。各学段独立递增。"""
    stage_prefix = {"primary": "A", "middle": "B", "high": "C"}
    used = {r.class_code for r in db.query(models.Class).all() if r.class_code}
    # 跨学段顺序生成：A01..A99, B01..B99, C01..C99
    for prefix in stage_prefix.values():
        for num in range(1, 100):
            code = f"{prefix}{num:02d}"
            if code not in used:
                return code
    raise ValidationError("班级编号已用完(A01-C99)")


def _next_teacher_code(db: Session) -> str:
    """教师工号：T + 3 位数字（T001..T999）。"""
    max_seq = 0
    for r in db.query(models.Teacher).all():
        code = r.teacher_code or ""
        if code.startswith("T") and len(code) >= 4:
            try:
                seq = int(code[1:])
                max_seq = max(max_seq, seq)
            except ValueError:
                continue
    if max_seq >= 999:
        raise ValidationError("教师工号已用完(T001-T999)")
    return f"T{max_seq + 1:03d}"


@router.get("/next-code")
def next_code(
    type: str = Query(..., description="student | class | teacher"),
    _: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    if type == "student":
        code = _next_student_code(db)
    elif type == "class":
        code = _next_class_code(db)
    elif type == "teacher":
        code = _next_teacher_code(db)
    else:
        raise ValidationError("type 必须是 student / class / teacher")
    return {"type": type, "code": code}
