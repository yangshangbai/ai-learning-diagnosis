"""题库接口。

端点：
  GET    /api/v1/questions          列表（subject_id/grade_id/ques_type/category_id/q 过滤）
  GET    /api/v1/questions/{id}     详情
  POST   /api/v1/questions          新建（自动生成位置编码）
  PUT    /api/v1/questions/{id}     更新
  DELETE /api/v1/questions/{id}     删除（物理删除，解除试卷快照引用）
  POST   /api/v1/questions/import   批量导入（按 source_id 去重覆盖）

位置编码规则 §4.4：学科码(3字母)-年级码(G+数字)-知识点码(KP+3位)-序号(4位)，如 MAT-G7-KP003-0027。
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.errors import NotFoundError, ValidationError, ConflictError, ForbiddenError
from ..core.logging import logger
from ..core.security import Principal, require_auth, require_permission
from ..schemas.question import (
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
    PaginatedQuestion,
    QuestionImportRequest,
)

router = APIRouter(prefix="/api/v1/questions", tags=["question-bank"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_question_code(db: Session, subject_id, grade_id, knowledge_id) -> str:
    subj = db.query(models.Category).filter(models.Category.id == subject_id).first() if subject_id else None
    grade = db.query(models.Category).filter(models.Category.id == grade_id).first() if grade_id else None
    kp = db.query(models.Category).filter(models.Category.id == knowledge_id).first() if knowledge_id else None
    sc = subj.code if subj and subj.code else "SUB"
    gc = grade.code if grade and grade.code else "G0"
    kc = kp.code if kp and kp.code else "KP000"
    prefix = f"{sc}-{gc}-{kc}-"
    rows = db.query(models.Question).filter(models.Question.question_code.like(f"{prefix}%")).all()
    max_seq = 0
    for r in rows:
        try:
            seq = int(r.question_code.split("-")[-1])
            max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            continue
    if max_seq >= 9999:
        raise ConflictError("题目序号已用完(9999)")
    return f"{prefix}{max_seq + 1:04d}"


def _to_question_out(db: Session, q: models.Question) -> QuestionOut:
    out = QuestionOut.model_validate(q)
    if q.subject_id:
        s = db.query(models.Category).filter(models.Category.id == q.subject_id).first()
        out.subject_name = s.name if s else None
    if q.grade_id:
        g = db.query(models.Category).filter(models.Category.id == q.grade_id).first()
        out.grade_name = g.name if g else None
    if q.category_id:
        c = db.query(models.Category).filter(models.Category.id == q.category_id).first()
        out.category_name = c.name if c else None
    return out


@router.get("", response_model=PaginatedQuestion)
def list_questions(
    subject_id: Optional[int] = None,
    grade_id: Optional[int] = None,
    ques_type: Optional[str] = None,
    category_id: Optional[int] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    principal: Principal = Depends(require_permission("question","view")),
    db: Session = Depends(get_db),
):
    query = db.query(models.Question).filter(models.Question.status != "archived")
    if subject_id:
        query = query.filter(models.Question.subject_id == subject_id)
    if grade_id:
        query = query.filter(models.Question.grade_id == grade_id)
    if ques_type:
        query = query.filter(models.Question.ques_type == ques_type)
    if category_id:
        query = query.filter(models.Question.category_id == category_id)
    if q:
        query = query.filter(models.Question.stem.ilike(f"%{q}%"))
    total = query.count()
    rows = (
        query.order_by(desc(models.Question.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedQuestion(
        items=[_to_question_out(db, r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{qid}", response_model=QuestionOut)
def get_question(qid: int, principal: Principal = Depends(require_permission("question","view")), db: Session = Depends(get_db)):
    q = db.query(models.Question).filter(models.Question.id == qid).first()
    if not q:
        raise NotFoundError("题目", qid)
    return _to_question_out(db, q)


@router.post("", response_model=QuestionOut, status_code=201)
def create_question(body: QuestionCreate, _: Principal = Depends(require_permission("question", "add")), db: Session = Depends(get_db)):
    kid = body.knowledge_ids[0] if body.knowledge_ids else None
    code = generate_question_code(db, body.subject_id, body.grade_id, kid)
    q = models.Question(question_code=code, **body.model_dump())
    db.add(q)
    db.commit()
    db.refresh(q)
    logger.info("question_created", extra={"id": q.id, "code": code})
    return _to_question_out(db, q)


@router.put("/{qid}", response_model=QuestionOut)
def update_question(qid: int, body: QuestionUpdate, _: Principal = Depends(require_permission("question", "edit")), db: Session = Depends(get_db)):
    q = db.query(models.Question).filter(models.Question.id == qid).first()
    if not q:
        raise NotFoundError("题目", qid)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(q, k, v)
    db.commit()
    db.refresh(q)
    return _to_question_out(db, q)


@router.delete("/{qid}")
def delete_question(qid: int, _: Principal = Depends(require_permission("question", "delete")), db: Session = Depends(get_db)):
    """物理删除题目（单事务）。

    处理下游引用：
      1) paper_questions 快照：将 question_id 置 NULL（保留试卷快照与评分链路，question_id 可空）；
      2) question_images：级联删除题目图片；
      3) 删除 questions 行本身。
    """
    q = db.query(models.Question).filter(models.Question.id == qid).first()
    if not q:
        raise NotFoundError("题目", qid)
    # 1) 试卷快照：解除引用（不删行，避免破坏已组卷快照与 question_scores 链路）
    db.query(models.PaperQuestion).filter(models.PaperQuestion.question_id == qid).update(
        {models.PaperQuestion.question_id: None}, synchronize_session=False
    )
    # 2) 题目图片
    db.query(models.QuestionImage).filter(models.QuestionImage.question_id == qid).delete(
        synchronize_session=False
    )
    # 3) 题目本体
    db.delete(q)
    db.commit()
    logger.info("question_deleted", extra={"id": qid})
    return {"code": 0, "message": "deleted", "data": None}


def _resolve_category_id(db: Session, cat_type: str, name: str) -> Optional[int]:
    """按名称查找分类 id；不存在则自动创建（学科/年级 docx/OCR 导入用）。"""
    if not name or not str(name).strip():
        return None
    name = str(name).strip()
    row = (
        db.query(models.Category)
        .filter(models.Category.category_type == cat_type, models.Category.name == name)
        .first()
    )
    if row:
        if row.status != "active":
            row.status = "active"
            db.commit()
        return row.id
    # 自动创建（code 用名称前 3 位大写 + 时间戳防冲突）
    import hashlib, time
    code = "AUTO-%s" % hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    stage = "primary" if cat_type == "grade" and "年级" in name else None
    if cat_type == "grade":
        stage = "primary" if name.endswith("年级") else ("middle" if name.startswith(("初", "七", "八", "九")) else "high")
    extra = {"stage": stage} if stage else None
    row = models.Category(category_type=cat_type, name=name, code=code, sort_order=0, extra=extra)
    db.add(row)
    db.flush()
    return row.id


def _prepare_import_item(db: Session, it) -> dict:
    """把 import item 解析为 Question 可用的 dict：按名称解析学科/年级 id（缺失自动创建）。"""
    data = it.model_dump()
    if it.subject_name:
        data["subject_id"] = _resolve_category_id(db, "subject", it.subject_name)
    if it.grade_name:
        data["grade_id"] = _resolve_category_id(db, "grade", it.grade_name)
    # 去掉仅用于解析的字段（不进 Question 表）
    for k in ("subject_name", "grade_name"):
        data.pop(k, None)
    return data


@router.post("/import", response_model=PaginatedQuestion)
def import_questions(body: QuestionImportRequest, _: Principal = Depends(require_permission("question", "add")), db: Session = Depends(get_db)):
    created: List[models.Question] = []
    for it in body.items:
        item_data = _prepare_import_item(db, it)
        kid = it.knowledge_ids[0] if it.knowledge_ids else None
        code = generate_question_code(db, item_data["subject_id"], item_data["grade_id"], kid)
        if it.source_id:
            exist = db.query(models.Question).filter(models.Question.source_id == it.source_id).first()
            if exist:
                for k, v in item_data.items():
                    if k == "source_id":
                        continue
                    setattr(exist, k, v)
                exist.question_code = code
                db.commit()
                db.refresh(exist)
                created.append(exist)
                continue
        q = models.Question(question_code=code, **item_data)
        db.add(q)
        db.commit()
        db.refresh(q)
        created.append(q)
    return PaginatedQuestion(
        items=[_to_question_out(db, c) for c in created],
        total=len(created),
        page=1,
        page_size=len(created),
    )


# ---------------------------------------------------------------------------
# 批量操作：分类 / 标签 / 删除
# ---------------------------------------------------------------------------
class BatchCategoryBody(BaseModel):
    ids: List[int]
    category_id: Optional[int] = None  # None = 清除分类


class BatchTagsBody(BaseModel):
    ids: List[int]
    tags: List[str] = []
    append: bool = True  # True=追加到现有标签，False=覆盖


class BatchDeleteBody(BaseModel):
    ids: List[int]


def _valid_tag_ids(db: Session, tag_ids: List[str]) -> List[str]:
    """只保留 tags 表中真实存在的 id（容错：脏数据/被删标签自动过滤）。"""
    nums = []
    for t in tag_ids:
        try:
            nums.append(int(t))
        except (TypeError, ValueError):
            continue
    if not nums:
        return []
    exist = {str(r.id) for r in db.query(models.Tag).filter(models.Tag.id.in_(nums)).all()}
    return [str(n) for n in nums if str(n) in exist]


@router.post("/batch-category")
def batch_set_category(
    body: BatchCategoryBody,
    _: Principal = Depends(require_permission("question", "edit")),
    db: Session = Depends(get_db),
):
    """批量设置题目分类。body: {ids:[...], category_id:int|null}"""
    if not body.ids:
        raise ValidationError("ids 不能为空")
    if body.category_id is not None:
        cat = db.query(models.Category).filter(models.Category.id == body.category_id).first()
        if not cat:
            raise NotFoundError("分类", body.category_id)
    rows = db.query(models.Question).filter(models.Question.id.in_(body.ids)).all()
    if not rows:
        raise NotFoundError("题目", body.ids[0])
    n = 0
    for q in rows:
        q.category_id = body.category_id
        n += 1
    db.commit()
    logger.info("questions_batch_category", extra={"count": n, "category_id": body.category_id})
    return {"code": 0, "message": "ok", "updated": n}


@router.post("/batch-tags")
def batch_set_tags(
    body: BatchTagsBody,
    _: Principal = Depends(require_permission("question", "edit")),
    db: Session = Depends(get_db),
):
    """批量设置题目标签。body: {ids:[...], tags:[tagId...], append:bool}"""
    if not body.ids:
        raise ValidationError("ids 不能为空")
    valid = _valid_tag_ids(db, body.tags)
    rows = db.query(models.Question).filter(models.Question.id.in_(body.ids)).all()
    if not rows:
        raise NotFoundError("题目", body.ids[0])
    n = 0
    for q in rows:
        cur = [str(t) for t in (q.tags or [])]
        if body.append:
            merged = cur
            for t in valid:
                if t not in merged:
                    merged.append(t)
            q.tags = merged
        else:
            q.tags = list(valid)
        n += 1
    db.commit()
    logger.info("questions_batch_tags", extra={"count": n, "tags": valid, "append": body.append})
    return {"code": 0, "message": "ok", "updated": n}


@router.post("/batch-delete")
def batch_delete_questions(
    body: BatchDeleteBody,
    _: Principal = Depends(require_permission("question", "delete")),
    db: Session = Depends(get_db),
):
    """批量物理删除题目（单事务）。body: {ids:[...]}"""
    if not body.ids:
        raise ValidationError("ids 不能为空")
    rows = db.query(models.Question).filter(models.Question.id.in_(body.ids)).all()
    n = 0
    for q in rows:
        # 试卷快照：解除引用（保留快照与评分链路）
        db.query(models.PaperQuestion).filter(models.PaperQuestion.question_id == q.id).update(
            {models.PaperQuestion.question_id: None}, synchronize_session=False
        )
        # 题目图片
        db.query(models.QuestionImage).filter(models.QuestionImage.question_id == q.id).delete(
            synchronize_session=False
        )
        db.delete(q)
        n += 1
    db.commit()
    logger.info("questions_batch_delete", extra={"count": n})
    return {"code": 0, "message": "ok", "deleted": n}
