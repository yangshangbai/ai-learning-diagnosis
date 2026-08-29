"""基础数据接口：统一分类（含枚举与知识点树）。

端点：
  GET    /api/v1/categories          平铺列表（type/parent_id/q 过滤）
  GET    /api/v1/categories/tree     树形（按 type 返回，knowledge 展开 children）
  POST   /api/v1/categories          创建
  PUT    /api/v1/categories/{id}     更新
  DELETE /api/v1/categories/{id}     删除（有子节点或有业务引用则拒绝；否则物理删除）
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.errors import NotFoundError, ValidationError, ConflictError
from ..core.logging import logger
from ..core.security import Principal, require_auth, require_permission
from ..schemas.basic import CategoryCreate, CategoryOut, CategoryUpdate, PaginatedCategory

router = APIRouter(prefix="/api/v1/categories", tags=["basic-data"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _category_count(db: Session, cat: models.Category) -> int:
    """best-effort 统计该分类下业务实体数；无引用或非业务分类返回 0。"""
    try:
        t = cat.category_type
        if t in ("question", "question_bank"):
            return db.query(models.Question).filter(models.Question.category_id == cat.id).count()
        if t == "paper":
            return db.query(models.Paper).filter(models.Paper.category_id == cat.id).count()
        if t == "task":
            return db.query(models.ExamTask).filter(models.ExamTask.category_id == cat.id).count()
    except Exception:
        return 0
    return 0


def _to_out_with_count(db: Session, row: models.Category) -> CategoryOut:
    out = CategoryOut.model_validate(row)
    out.count = _category_count(db, row)
    return out


@router.get("", response_model=PaginatedCategory)
def list_categories(
    category_type: Optional[str] = Query(None, alias="type"),
    parent_id: Optional[int] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    _: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    query = db.query(models.Category)
    if category_type:
        query = query.filter(models.Category.category_type == category_type)
    if parent_id is not None:
        query = query.filter(models.Category.parent_id == parent_id)
    if q:
        query = query.filter(models.Category.name.ilike(f"%{q}%"))
    total = query.count()
    rows = (
        query.order_by(models.Category.sort_order, models.Category.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedCategory(
        items=[_to_out_with_count(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tree", response_model=List[CategoryOut])
def tree(
    category_type: str = Query(..., alias="type", description="按类型返回树，如 knowledge"),
    _: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    nodes = (
        db.query(models.Category)
        .filter(models.Category.category_type == category_type)
        .order_by(models.Category.sort_order, models.Category.id)
        .all()
    )
    by_id = {n.id: _to_out_with_count(db, n) for n in nodes}
    roots: List[CategoryOut] = []
    for nid, node in by_id.items():
        if node.parent_id and node.parent_id in by_id:
            by_id[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    body: CategoryCreate,
    _: Principal = Depends(require_permission("system", "add")),
    db: Session = Depends(get_db),
):
    if body.parent_id:
        parent = (
            db.query(models.Category)
            .filter(models.Category.id == body.parent_id)
            .first()
        )
        if not parent:
            raise NotFoundError("父分类", body.parent_id)
        if parent.category_type != body.category_type:
            raise ValidationError("父分类类型必须一致")
    row = models.Category(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("category_created", extra={"id": row.id, "type": row.category_type})
    return CategoryOut.model_validate(row)


@router.put("/{cat_id}", response_model=CategoryOut)
def update_category(
    cat_id: int,
    body: CategoryUpdate,
    _: Principal = Depends(require_permission("system", "edit")),
    db: Session = Depends(get_db),
):
    row = db.query(models.Category).filter(models.Category.id == cat_id).first()
    if not row:
        raise NotFoundError("分类", cat_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return CategoryOut.model_validate(row)


def _category_reference(db: Session, cat: models.Category) -> Optional[str]:
    """检查分类是否被业务数据引用；返回引用描述（如「题目…」「试卷…」），无引用返回 None。

    覆盖：题目/试卷的 category/subject/grade 引用、任务 category、知识点数组(knowledge_ids)、
    教师任教学科(subject_ids / TeacherClass.subject_id)。
    """
    cid = cat.id
    # 题目：category_id / subject_id / grade_id / knowledge_ids[]
    q = (
        db.query(models.Question)
        .filter(
            (models.Question.category_id == cid)
            | (models.Question.subject_id == cid)
            | (models.Question.grade_id == cid)
        )
        .first()
    )
    if q:
        return f"题目「{(q.stem or '')[:20]}」"
    for row in db.query(models.Question).filter(models.Question.knowledge_ids.isnot(None)).all():
        if cid in (row.knowledge_ids or []):
            return f"题目「{(row.stem or '')[:20]}」的知识点"
    # 试卷：category_id / subject_id / grade_id
    p = (
        db.query(models.Paper)
        .filter(
            (models.Paper.category_id == cid)
            | (models.Paper.subject_id == cid)
            | (models.Paper.grade_id == cid)
        )
        .first()
    )
    if p:
        return f"试卷「{(p.name or '')[:20]}」"
    # 任务：category_id
    t = db.query(models.ExamTask).filter(models.ExamTask.category_id == cid).first()
    if t:
        return f"考试任务「{(t.name or '')[:20]}」"
    # 教师任教学科 / 班级任课配置
    for tch in db.query(models.Teacher).filter(models.Teacher.subject_ids.isnot(None)).all():
        if cid in (tch.subject_ids or []):
            return f"教师「{(tch.name or '')[:20]}」任教学科"
    tc = db.query(models.TeacherClass).filter(models.TeacherClass.subject_id == cid).first()
    if tc:
        return "班级任课配置"
    return None


@router.delete("/{cat_id}")
def delete_category(
    cat_id: int,
    _: Principal = Depends(require_permission("system", "delete")),
    db: Session = Depends(get_db),
):
    row = db.query(models.Category).filter(models.Category.id == cat_id).first()
    if not row:
        raise NotFoundError("分类", cat_id)
    has_child = (
        db.query(models.Category)
        .filter(models.Category.parent_id == cat_id)
        .first()
    )
    if has_child:
        raise ConflictError("该分类存在子节点，请先删除子节点")
    # 业务引用校验：被题目/试卷/任务/教师等引用时拒绝物理删除（数据完整性保护）
    ref = _category_reference(db, row)
    if ref:
        raise ConflictError(f"该分类已被{ref}引用，无法删除")
    # 物理删除
    db.delete(row)
    db.commit()
    logger.info("category_deleted", extra={"id": cat_id})
    return {"code": 0, "message": "deleted", "data": None}


class ReorderItem(BaseModel):
    id: int
    sort_order: int


class ReorderBody(BaseModel):
    items: List[ReorderItem]


@router.post("/reorder")
def reorder_categories(
    body: ReorderBody,
    _: Principal = Depends(require_permission("system", "edit")),
    db: Session = Depends(get_db),
):
    """批量更新分类排序。body: {items:[{id, sort_order}, ...]}"""
    updated = 0
    for it in body.items:
        row = db.query(models.Category).filter(models.Category.id == it.id).first()
        if not row:
            continue
        row.sort_order = it.sort_order
        updated += 1
    db.commit()
    return {"code": 0, "message": "ok", "updated": updated}
