"""教师接口。

端点：
  GET    /api/v1/teachers          列表（分页；教师角色仅看本人）
  GET    /api/v1/teachers/{id}     详情
  POST   /api/v1/teachers          新建（同步创建 User 登录账号）
  PUT    /api/v1/teachers/{id}     更新
  DELETE /api/v1/teachers/{id}     删除（物理删除，级联删 TeacherClass 与 User 账号）
  POST   /api/v1/teachers/{id}/classes  设置关联班级（班主任唯一性校验）

权限：教师仅可查看/编辑本人；管理员全量。
"""
import hashlib
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.errors import NotFoundError, ValidationError, ConflictError, ForbiddenError
from ..core.logging import logger
from ..core.security import Principal, default_teacher_permissions, require_auth, require_permission
from ..schemas.teacher import (
    TeacherCreate,
    TeacherOut,
    TeacherUpdate,
    PaginatedTeacher,
    TeacherClassItem,
)

router = APIRouter(prefix="/api/v1/teachers", tags=["teacher"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _to_out(db: Session, t: models.Teacher) -> TeacherOut:
    user = db.query(models.User).filter(models.User.id == t.user_id).first() if t.user_id else None
    class_ids = [tc.class_id for tc in db.query(models.TeacherClass).filter(models.TeacherClass.teacher_id == t.id)]
    out = TeacherOut.model_validate(t)
    out.username = user.username if user else None
    out.class_ids = class_ids
    return out


@router.get("", response_model=PaginatedTeacher)
def list_teachers(
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    principal: Principal = Depends(require_permission("teacher","view")),
    db: Session = Depends(get_db),
):
    query = db.query(models.Teacher)
    if principal.role == "teacher":
        query = query.filter(models.Teacher.id == principal.teacher_id)
    if q:
        query = query.filter(models.Teacher.name.ilike(f"%{q}%"))
    total = query.count()
    rows = (
        query.order_by(desc(models.Teacher.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedTeacher(
        items=[_to_out(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{teacher_id}", response_model=TeacherOut)
def get_teacher(
    teacher_id: int,
    principal: Principal = Depends(require_permission("teacher","view")),
    db: Session = Depends(get_db),
):
    t = db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()
    if not t:
        raise NotFoundError("教师", teacher_id)
    if principal.role == "teacher" and principal.teacher_id != teacher_id:
        raise ForbiddenError("仅可查看本人信息")
    return _to_out(db, t)


@router.post("", response_model=TeacherOut, status_code=201)
def create_teacher(
    body: TeacherCreate,
    _: Principal = Depends(require_permission("teacher", "add")),
    db: Session = Depends(get_db),
):
    exists = db.query(models.User).filter(models.User.username == body.username).first()
    if exists:
        raise ConflictError("登录账号已存在")
    user = models.User(
        username=body.username,
        password_hash=_hash(body.password),
        name=body.name,
        role="teacher",
        permissions=default_teacher_permissions(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    t = models.Teacher(
        user_id=user.id,
        name=body.name,
        gender=body.gender,
        phone=body.phone,
        subject_ids=body.subject_ids,
        remark=body.remark,
        status="active",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    # 回填工号 T + 4 位流水
    t.teacher_code = "T" + str(t.id).zfill(4)
    db.commit()
    db.refresh(t)
    user.teacher_id = t.id
    db.commit()
    # 关联班级
    if body.classes:
        _apply_classes(db, t.id, body.classes)
    logger.info("teacher_created", extra={"id": t.id, "username": body.username})
    return _to_out(db, t)


def _apply_classes(db: Session, teacher_id: int, items: List[TeacherClassItem]):
    # 清除旧关联
    db.query(models.TeacherClass).filter(models.TeacherClass.teacher_id == teacher_id).delete()
    for it in items:
        if it.role == "head_teacher":
            existing = (
                db.query(models.TeacherClass)
                .filter(
                    models.TeacherClass.class_id == it.class_id,
                    models.TeacherClass.role == "head_teacher",
                )
                .first()
            )
            if existing and existing.teacher_id != teacher_id:
                raise ConflictError(f"班级 {it.class_id} 已存在班主任")
        db.add(
            models.TeacherClass(
                teacher_id=teacher_id,
                class_id=it.class_id,
                role=it.role,
                subject_id=it.subject_id,
            )
        )
    db.commit()


@router.post("/{teacher_id}/classes", response_model=TeacherOut)
def set_classes(
    teacher_id: int,
    items: List[TeacherClassItem],
    principal: Principal = Depends(require_permission("teacher", "edit")),
    db: Session = Depends(get_db),
):
    t = db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()
    if not t:
        raise NotFoundError("教师", teacher_id)
    if principal.role == "teacher" and principal.teacher_id != teacher_id:
        raise ForbiddenError("仅可设置本人关联班级")
    _apply_classes(db, teacher_id, items)
    return _to_out(db, t)


@router.put("/{teacher_id}", response_model=TeacherOut)
def update_teacher(
    teacher_id: int,
    body: TeacherUpdate,
    principal: Principal = Depends(require_permission("teacher", "edit")),
    db: Session = Depends(get_db),
):
    t = db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()
    if not t:
        raise NotFoundError("教师", teacher_id)
    if principal.role == "teacher" and principal.teacher_id != teacher_id:
        raise ForbiddenError("仅可编辑本人信息")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return _to_out(db, t)


@router.delete("/{teacher_id}")
def delete_teacher(
    teacher_id: int,
    _: Principal = Depends(require_permission("teacher", "delete")),
    db: Session = Depends(get_db),
):
    """物理删除教师（单事务）。

    处理下游引用：
      1) TeacherClass 班级关联：级联删除；
      2) ExamTask.creator_id（可空）：置 NULL，保留其创建的任务；
      3) User 登录账号（该教师注册时同步创建）：级联删除，账号一并注销。
    """
    t = db.query(models.Teacher).filter(models.Teacher.id == teacher_id).first()
    if not t:
        raise NotFoundError("教师", teacher_id)
    # 1) 班级关联
    db.query(models.TeacherClass).filter(models.TeacherClass.teacher_id == teacher_id).delete(
        synchronize_session=False
    )
    # 2) 其创建的任务 creator_id 置空（可空字段）
    db.query(models.ExamTask).filter(models.ExamTask.creator_id == teacher_id).update(
        {models.ExamTask.creator_id: None}, synchronize_session=False
    )
    # 3) 教师本体（命令式删除：Teacher/User 无 relationship()，ORM 不排序表级外键，
    #    必须先发 teachers 的 DELETE 再删 users，否则 teachers_user_id_fkey 违约——BUG-L011）
    db.query(models.Teacher).filter(models.Teacher.id == teacher_id).delete(
        synchronize_session=False
    )
    # 4) 关联的登录账号（教师与 User 一一对应，删教师即注销账号）
    if t.user_id:
        u = db.query(models.User).filter(models.User.id == t.user_id).first()
        if u:
            db.delete(u)
    db.commit()
    logger.info("teacher_deleted", extra={"id": teacher_id})
    return {"code": 0, "message": "deleted", "data": None}
