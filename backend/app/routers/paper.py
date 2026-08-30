"""试卷接口。

端点：
  GET    /api/v1/papers             列表（分页）
  GET    /api/v1/papers/{id}        详情（含试题快照）
  POST   /api/v1/papers             组卷（选题→自动带答案→计算总分/题数）
  PUT    /api/v1/papers/{id}        更新
  DELETE /api/v1/papers/{id}        删除（真删除，级联清除考试任务/答题卡/评分）
  POST   /api/v1/papers/{id}/answer-sheet  生成答题卡模板（按题型宽度 §5.4）

试卷模板（新增，见 试题答题卡模板方案V2.md §2.1）：
  GET    /api/v1/papers/{id}/template/paper   下载试卷模板（无则自动生成）
  GET    /api/v1/papers/{id}/template/sheet   下载答题卡模板（无则自动生成）
  POST   /api/v1/papers/{id}/template/paper   上传覆盖试卷模板
  POST   /api/v1/papers/{id}/template/sheet   上传覆盖答题卡模板
  GET    /api/v1/papers/{id}/template/meta    模板元信息（source/file_name/file_size/...）
  DELETE /api/v1/papers/{id}/template/paper   恢复默认试卷模板
  DELETE /api/v1/papers/{id}/template/sheet   恢复默认答题卡模板

试卷编号：P + YYYYMMDD + 3 位流水（系统生成）。
宽度规则 §5.4：单选/多选 15mm、判断 10mm、填空 40mm、解答 100% 宽（高度=分值×10mm，8 分≈80mm）。
"""
import datetime
import os
import time
import zipfile
from typing import Optional, List
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse

from .. import models
from .. import template_engine as tpl_engine
from ..core.db import SessionLocal
from ..core.errors import NotFoundError, ValidationError, ConflictError, AppError
from ..core.logging import logger
from ..core.security import Principal, require_auth, require_permission
from ..schemas.paper import (
    PaperCreate,
    PaperOut,
    PaperUpdate,
    PaginatedPaper,
    AnswerSheetTemplateOut,
    PaperQuestionOut,
)
from ..schemas.template import PaperTemplateOut, TemplateMetaOut

router = APIRouter(prefix="/api/v1/papers", tags=["paper"])

# 模板文件大小上限（10MB）
MAX_TEMPLATE_BYTES = 10 * 1024 * 1024


class BadRequestError(AppError):
    """400 客户端错误（扩展名/参数不合法），与项目错误体系同构。"""

    def __init__(self, message: str):
        super().__init__(message, "BAD_REQUEST", 400)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_paper_code(db: Session) -> str:
    d = datetime.datetime.now().strftime("%Y%m%d")
    prefix = f"P{d}-"
    rows = db.query(models.Paper).filter(models.Paper.paper_code.like(f"{prefix}%")).all()
    max_seq = 0
    for r in rows:
        try:
            seq = int(r.paper_code.split("-")[-1])
            max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            continue
    if max_seq >= 999:
        raise ConflictError("试卷编号已用完(999)")
    return f"{prefix}{max_seq + 1:03d}"


def _build_layout(paper_id: int, db: Session) -> dict:
    pqs = (
        db.query(models.PaperQuestion)
        .filter(models.PaperQuestion.paper_id == paper_id)
        .order_by(models.PaperQuestion.sort_order)
        .all()
    )
    choice, fill, essay = [], [], []
    for pq in pqs:
        q = db.query(models.Question).filter(models.Question.id == pq.question_id).first()
        qt = q.ques_type if q else "essay"
        entry = {"paper_question_id": pq.id, "question_number": pq.sort_order, "score": pq.score}
        if qt in ("single_choice", "multi_choice", "true_false"):
            w = 10 if qt == "true_false" else 15
            choice.append({**entry, "width_mm": w})
        elif qt == "fill_blank":
            fill.append({**entry, "width_mm": 40})
        else:
            essay.append({**entry, "height_mm": max(40, (pq.score or 8) * 10)})
    sections = []
    if choice:
        sections.append({"type": "choice", "questions": choice, "width_mm": sum(c["width_mm"] for c in choice)})
    if fill:
        sections.append({"type": "fill", "questions": fill, "width_mm": sum(f["width_mm"] for f in fill)})
    if essay:
        sections.append({"type": "essay", "questions": essay, "height_mm": sum(e["height_mm"] for e in essay)})
    return {"page_size": "A4", "sections": sections}


def _paper_question_ids(paper_id: int, db: Session) -> List[int]:
    rows = (
        db.query(models.PaperQuestion)
        .filter(models.PaperQuestion.paper_id == paper_id)
        .order_by(models.PaperQuestion.sort_order)
        .all()
    )
    return [r.question_id for r in rows if r.question_id is not None]


def _to_paper_out(p: models.Paper, db: Session) -> PaperOut:
    out = PaperOut.model_validate(p)
    out.questions = _paper_question_ids(p.id, db)
    if p.subject_id:
        s = db.query(models.Category).filter(models.Category.id == p.subject_id).first()
        out.subject = s.name if s else None
    if p.grade_id:
        g = db.query(models.Category).filter(models.Category.id == p.grade_id).first()
        out.grade = g.name if g else None
    if p.category_id:
        c = db.query(models.Category).filter(models.Category.id == p.category_id).first()
        out.category = c.name if c else None
    return out


@router.get("", response_model=PaginatedPaper)
def list_papers(
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    principal: Principal = Depends(require_permission("paper","view")),
    db: Session = Depends(get_db),
):
    query = db.query(models.Paper).filter(models.Paper.status != "archived")
    if q:
        query = query.filter(models.Paper.name.ilike(f"%{q}%"))
    total = query.count()
    rows = (
        query.order_by(desc(models.Paper.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedPaper(
        items=[_to_paper_out(r, db) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{paper_id}", response_model=PaperOut)
def get_paper(paper_id: int, principal: Principal = Depends(require_permission("paper","view")), db: Session = Depends(get_db)):
    p = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not p:
        raise NotFoundError("试卷", paper_id)
    return _to_paper_out(p, db)


@router.get("/{paper_id}/questions", response_model=List[PaperQuestionOut])
def list_paper_questions(
    paper_id: int,
    principal: Principal = Depends(require_permission("paper","view")),
    db: Session = Depends(get_db),
):
    """试卷试题快照：返回组卷时写入的 PaperQuestion（含排序/分值/答案/解析），并附带题干。"""
    p = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not p:
        raise NotFoundError("试卷", paper_id)
    rows = (
        db.query(models.PaperQuestion)
        .filter(models.PaperQuestion.paper_id == paper_id)
        .order_by(models.PaperQuestion.sort_order)
        .all()
    )
    items = []
    for pq in rows:
        q = db.query(models.Question).filter(models.Question.id == pq.question_id).first()
        out = PaperQuestionOut.model_validate(pq).model_dump()
        out["stem"] = q.stem if q else ""
        items.append(out)
    return items


@router.post("", response_model=PaperOut, status_code=201)
def create_paper(body: PaperCreate, _: Principal = Depends(require_permission("paper", "add")), db: Session = Depends(get_db)):
    code = generate_paper_code(db)
    p = models.Paper(
        paper_code=code,
        name=body.name,
        category_id=body.category_id,
        subject_id=body.subject_id,
        grade_id=body.grade_id,
        remark=body.remark,
        status="draft",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    total = 0
    for i, qid in enumerate(body.question_ids):
        q = db.query(models.Question).filter(models.Question.id == qid).first()
        if not q:
            continue
        db.add(
            models.PaperQuestion(
                paper_id=p.id,
                question_id=qid,
                ques_type=q.ques_type,
                sort_order=i + 1,
                score=q.score or 0,
                answer_key=q.answer,
                analysis=q.analysis,
            )
        )
        total += q.score or 0
    db.commit()
    p.total_score = total
    p.question_count = len(body.question_ids)
    db.commit()
    db.refresh(p)
    logger.info("paper_created", extra={"id": p.id, "code": code, "count": p.question_count})
    return _to_paper_out(p, db)


@router.put("/{paper_id}", response_model=PaperOut)
def update_paper(paper_id: int, body: PaperUpdate, _: Principal = Depends(require_permission("paper", "edit")), db: Session = Depends(get_db)):
    p = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not p:
        raise NotFoundError("试卷", paper_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return _to_paper_out(p, db)


@router.delete("/{paper_id}")
def delete_paper(paper_id: int, _: Principal = Depends(require_permission("paper", "delete")), db: Session = Depends(get_db)):
    """真删除试卷及其关联业务数据（单事务，先子后父）。

    级联链：
      papers ── paper_questions / answer_sheet_templates
            └─ exam_tasks ── task_assignments / task_statistics / answer_sheets ── question_scores
    前端删除前已弹确认提示告知用户关联数据将一并清除。
    """
    p = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not p:
        raise NotFoundError("试卷", paper_id)

    # 引用该试卷的全部考试任务（含 voided，一并删除）
    task_ids = [
        row[0]
        for row in db.query(models.ExamTask.id)
        .filter(models.ExamTask.paper_id == paper_id)
        .all()
    ]

    # 先子后父：评分 → 答题卡 → 分配 → 统计 → 任务本体
    if task_ids:
        db.query(models.QuestionScore).filter(
            models.QuestionScore.task_id.in_(task_ids)
        ).delete(synchronize_session=False)
        db.query(models.AnswerSheet).filter(
            models.AnswerSheet.task_id.in_(task_ids)
        ).delete(synchronize_session=False)
        db.query(models.TaskAssignment).filter(
            models.TaskAssignment.task_id.in_(task_ids)
        ).delete(synchronize_session=False)
        db.query(models.TaskStatistic).filter(
            models.TaskStatistic.task_id.in_(task_ids)
        ).delete(synchronize_session=False)
        db.query(models.ExamTask).filter(
            models.ExamTask.paper_id == paper_id
        ).delete(synchronize_session=False)

    # 试卷题目快照与答题卡模板（先于试卷本体）
    db.query(models.PaperQuestion).filter(
        models.PaperQuestion.paper_id == paper_id
    ).delete(synchronize_session=False)
    db.query(models.AnswerSheetTemplate).filter(
        models.AnswerSheetTemplate.paper_id == paper_id
    ).delete(synchronize_session=False)

    # 试卷本体
    db.delete(p)
    db.commit()
    logger.info("paper_deleted", extra={"id": paper_id, "task_count": len(task_ids)})
    return {"code": 0, "message": "deleted", "data": None}


@router.post("/{paper_id}/answer-sheet", response_model=AnswerSheetTemplateOut, status_code=201)
def generate_answer_sheet(paper_id: int, _: Principal = Depends(require_permission("paper", "add")), db: Session = Depends(get_db)):
    p = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not p:
        raise NotFoundError("试卷", paper_id)
    layout = _build_layout(paper_id, db)
    existing = db.query(models.AnswerSheetTemplate).filter(models.AnswerSheetTemplate.paper_id == paper_id).first()
    if existing:
        existing.layout_config = layout
        db.commit()
        db.refresh(existing)
        return AnswerSheetTemplateOut.model_validate(existing)
    tpl = models.AnswerSheetTemplate(paper_id=paper_id, layout_config=layout)
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return AnswerSheetTemplateOut.model_validate(tpl)


# ===========================================================================
# 试卷模板 & 答题卡模板（文件模板：下载/上传覆盖/元信息/恢复默认）
# 见 《试题答题卡模板方案V2.md》§1/§2.1/§3
# ===========================================================================
def _get_paper(db: Session, paper_id: int) -> models.Paper:
    p = db.query(models.Paper).filter(models.Paper.id == paper_id).first()
    if not p:
        raise NotFoundError("试卷", paper_id)
    return p


def _category_name(db: Session, cid) -> str:
    if not cid:
        return ""
    c = db.query(models.Category).filter(models.Category.id == cid).first()
    return c.name if c else ""


def _paper_meta(paper: models.Paper, db: Session) -> dict:
    """引擎所需的试卷元信息（学科/年级/分类取中文名）。"""
    return {
        "paper_code": paper.paper_code,
        "name": paper.name,
        "subject": _category_name(db, paper.subject_id),
        "grade": _category_name(db, paper.grade_id),
        "category": _category_name(db, paper.category_id),
        "question_count": paper.question_count,
        "total_score": paper.total_score,
    }


def _load_paper_questions(db: Session, paper_id: int) -> List[dict]:
    """加载试卷题目快照（按 sort_order），附真实 Question 的 type/stem/options/answer。"""
    rows = (
        db.query(models.PaperQuestion)
        .filter(models.PaperQuestion.paper_id == paper_id)
        .order_by(models.PaperQuestion.sort_order)
        .all()
    )
    items = []
    for pq in rows:
        q = db.query(models.Question).filter(models.Question.id == pq.question_id).first()
        items.append(
            {
                "type": q.ques_type if q else "essay",
                "stem": q.stem if q else "",
                "options": q.options if q else [],
                "answer": pq.answer_key or (q.answer if q else ""),
                "score": pq.score or 0,
            }
        )
    return items


def _has_questions(db: Session, paper_id: int) -> bool:
    return (
        db.query(models.PaperQuestion)
        .filter(models.PaperQuestion.paper_id == paper_id)
        .first()
        is not None
    )


def _to_tpl_out(row) -> PaperTemplateOut:
    if not row:
        return PaperTemplateOut()
    exists = bool(row.file_path and os.path.isfile(row.file_path))
    return PaperTemplateOut(
        source=row.source,
        file_name=row.file_name,
        file_type=row.file_type,
        file_size=row.file_size or 0,
        file_path=row.file_path,
        updated_at=row.updated_at,
        exists=exists,
    )


def _download_response(path: str, filename: str, media_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document") -> FileResponse:
    """文件下载响应：Content-Disposition 用 filename*=UTF-8'' 编码中文文件名。"""
    safe_name = filename or os.path.basename(path)
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(safe_name, safe="")},
    )


def _ensure_paper_template(db: Session, paper: models.Paper) -> models.PaperTemplate:
    """确保试卷模板可用：用户版文件存在则返回；否则懒生成系统默认版（文件丢失时 source 回落 auto）。"""
    row = db.query(models.PaperTemplate).filter(models.PaperTemplate.paper_id == paper.id).first()
    if row and row.source == "user" and row.file_path and os.path.isfile(row.file_path):
        return row
    if not _has_questions(db, paper.id):
        raise ValidationError("试卷无题目，无法生成模板")
    questions = _load_paper_questions(db, paper.id)
    out_path = os.path.join(tpl_engine.get_template_dir(), "paper_%d_%d.docx" % (paper.id, int(time.time() * 1000)))
    tpl_engine.generate_paper_template_docx(_paper_meta(paper, db), questions, out_path)
    fname = "试卷模板_%s.docx" % (paper.name or paper.paper_code or paper.id)
    size = os.path.getsize(out_path)
    if row:
        row.file_path = out_path
        row.file_name = fname
        row.file_type = "docx"
        row.file_size = size
        row.source = "auto"
    else:
        row = models.PaperTemplate(
            paper_id=paper.id,
            file_path=out_path,
            file_name=fname,
            file_type="docx",
            file_size=size,
            source="auto",
            layout_config=_build_layout(paper.id, db),
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _ensure_sheet_template(db: Session, paper: models.Paper) -> models.AnswerSheetTemplate:
    """确保答题卡模板可用：用户版文件存在则返回；否则懒生成系统默认版并落 layout_config。"""
    row = db.query(models.AnswerSheetTemplate).filter(models.AnswerSheetTemplate.paper_id == paper.id).first()
    if row and row.source == "user" and row.file_path and os.path.isfile(row.file_path):
        return row
    if not _has_questions(db, paper.id):
        raise ValidationError("试卷无题目，无法生成模板")
    questions = _load_paper_questions(db, paper.id)
    out_path = os.path.join(tpl_engine.get_template_dir(), "sheet_%d_%d.docx" % (paper.id, int(time.time() * 1000)))
    tpl_engine.generate_sheet_template_docx(_paper_meta(paper, db), questions, out_path)
    layout = _build_layout(paper.id, db)
    fname = "答题卡模板_%s.docx" % (paper.name or paper.paper_code or paper.id)
    size = os.path.getsize(out_path)
    if row:
        row.file_path = out_path
        row.file_name = fname
        row.file_type = "docx"
        row.file_size = size
        row.source = "auto"
        row.layout_config = layout
    else:
        row = models.AnswerSheetTemplate(
            paper_id=paper.id,
            file_path=out_path,
            file_name=fname,
            file_type="docx",
            file_size=size,
            source="auto",
            layout_config=layout,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _is_valid_docx(path: str) -> bool:
    """校验 docx 是否为有效 Word 文档（zip 容器 + python-docx 可打开）。"""
    if not zipfile.is_zipfile(path):
        return False
    try:
        from docx import Document

        Document(path)
        return True
    except Exception:
        return False


def _check_upload_ext(filename: str, allow_doc: bool) -> str:
    """校验上传扩展名；返回小写扩展名（不含点）。"""
    ext = os.path.splitext(filename or "")[1].lower()
    allowed = {".docx", ".doc"} if allow_doc else {".docx"}
    if ext not in allowed:
        raise BadRequestError("仅支持 %s 格式的文件，当前上传文件类型为「%s」" % ("/".join(sorted(allowed)), ext or "未知"))
    return ext


def _save_upload(file: UploadFile) -> str:
    """流式写临时文件并限制 10MB；返回临时文件路径。"""
    tmp_dir = tpl_engine.get_template_dir()
    os.makedirs(tmp_dir, exist_ok=True)
    tmp = os.path.join(tmp_dir, ".upload_tmp_%d_%s" % (int(time.time() * 1000), os.urandom(4).hex()))
    total = 0
    try:
        with open(tmp, "wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_TEMPLATE_BYTES:
                    raise HTTPException(status_code=413, detail="文件超过 10MB，无法上传")
                f.write(chunk)
    except Exception:
        if os.path.isfile(tmp):
            os.remove(tmp)
        raise
    return tmp


# ---------------- 下载（懒生成） ----------------
@router.get("/{paper_id}/template/paper")
def download_paper_template(
    paper_id: int,
    _: Principal = Depends(require_permission("paper","view")),
    db: Session = Depends(get_db),
):
    p = _get_paper(db, paper_id)
    row = _ensure_paper_template(db, p)
    return _download_response(row.file_path, row.file_name)


@router.get("/{paper_id}/template/sheet")
def download_sheet_template(
    paper_id: int,
    _: Principal = Depends(require_permission("paper","view")),
    db: Session = Depends(get_db),
):
    p = _get_paper(db, paper_id)
    row = _ensure_sheet_template(db, p)
    return _download_response(row.file_path, row.file_name)


# ---------------- 上传覆盖 ----------------
@router.post("/{paper_id}/template/paper", response_model=PaperTemplateOut)
def upload_paper_template(
    paper_id: int,
    file: UploadFile = File(...),
    principal: Principal = Depends(require_permission("paper", "edit")),
    db: Session = Depends(get_db),
):
    p = _get_paper(db, paper_id)
    ext = _check_upload_ext(file.filename, allow_doc=True)
    tmp = _save_upload(file)
    if ext == ".docx" and not _is_valid_docx(tmp):
        os.remove(tmp)
        raise ValidationError("文件已损坏，无法解析，请上传有效的 Word 文档")
    final = os.path.join(
        tpl_engine.get_template_dir(),
        "paper_%d_%d%s" % (paper_id, int(time.time() * 1000), ext),
    )
    os.replace(tmp, final)
    row = db.query(models.PaperTemplate).filter(models.PaperTemplate.paper_id == paper_id).first()
    if not row:
        row = models.PaperTemplate(paper_id=paper_id)
        db.add(row)
    row.file_path = final
    row.file_name = file.filename or os.path.basename(final)
    row.file_type = "docx"
    row.file_size = os.path.getsize(final)
    row.source = "user"
    row.updated_by = principal.user_id
    # 结构模板：以数据库为准（题库快照是最可靠布局来源）
    row.layout_config = _build_layout(paper_id, db)
    db.commit()
    db.refresh(row)
    logger.info("paper_template_uploaded", extra={"paper_id": paper_id, "file": row.file_name, "size": row.file_size})
    return PaperTemplateOut.model_validate(row)


@router.post("/{paper_id}/template/sheet", response_model=PaperTemplateOut)
def upload_sheet_template(
    paper_id: int,
    file: UploadFile = File(...),
    principal: Principal = Depends(require_permission("paper", "edit")),
    db: Session = Depends(get_db),
):
    p = _get_paper(db, paper_id)
    ext = _check_upload_ext(file.filename, allow_doc=False)
    tmp = _save_upload(file)
    if not _is_valid_docx(tmp):
        os.remove(tmp)
        raise ValidationError("文件已损坏，无法解析，请上传有效的 Word 文档")
    final = os.path.join(
        tpl_engine.get_template_dir(),
        "sheet_%d_%d%s" % (paper_id, int(time.time() * 1000), ext),
    )
    os.replace(tmp, final)
    row = db.query(models.AnswerSheetTemplate).filter(models.AnswerSheetTemplate.paper_id == paper_id).first()
    if not row:
        row = models.AnswerSheetTemplate(paper_id=paper_id)
        db.add(row)
    row.file_path = final
    row.file_name = file.filename or os.path.basename(final)
    row.file_type = "docx"
    row.file_size = os.path.getsize(final)
    row.source = "user"
    row.layout_config = _build_layout(paper_id, db)
    db.commit()
    db.refresh(row)
    logger.info("sheet_template_uploaded", extra={"paper_id": paper_id, "file": row.file_name, "size": row.file_size})
    return PaperTemplateOut.model_validate(row)


# ---------------- 元信息 ----------------
@router.get("/{paper_id}/template/meta", response_model=TemplateMetaOut)
def get_template_meta(
    paper_id: int,
    _: Principal = Depends(require_permission("paper","view")),
    db: Session = Depends(get_db),
):
    p = _get_paper(db, paper_id)
    pt = db.query(models.PaperTemplate).filter(models.PaperTemplate.paper_id == paper_id).first()
    st = db.query(models.AnswerSheetTemplate).filter(models.AnswerSheetTemplate.paper_id == paper_id).first()
    return TemplateMetaOut(paper_template=_to_tpl_out(pt), sheet_template=_to_tpl_out(st))


# ---------------- 恢复默认 ----------------
@router.delete("/{paper_id}/template/paper")
def reset_paper_template(
    paper_id: int,
    principal: Principal = Depends(require_permission("paper", "edit")),
    db: Session = Depends(get_db),
):
    p = _get_paper(db, paper_id)
    row = db.query(models.PaperTemplate).filter(models.PaperTemplate.paper_id == paper_id).first()
    if row and row.file_path and os.path.isfile(row.file_path):
        try:
            os.remove(row.file_path)
        except OSError:
            pass
    if not row:
        row = models.PaperTemplate(paper_id=paper_id)
        db.add(row)
    row.file_path = None
    row.file_name = None
    row.file_type = "docx"
    row.file_size = 0
    row.source = "auto"
    row.updated_by = principal.user_id
    db.commit()
    db.refresh(row)
    logger.info("paper_template_reset", extra={"paper_id": paper_id})
    return {"code": 0, "message": "已恢复系统默认模板，下次下载将自动生成", "data": PaperTemplateOut.model_validate(row)}


@router.delete("/{paper_id}/template/sheet")
def reset_sheet_template(
    paper_id: int,
    principal: Principal = Depends(require_permission("paper", "edit")),
    db: Session = Depends(get_db),
):
    p = _get_paper(db, paper_id)
    row = db.query(models.AnswerSheetTemplate).filter(models.AnswerSheetTemplate.paper_id == paper_id).first()
    if row and row.file_path and os.path.isfile(row.file_path):
        try:
            os.remove(row.file_path)
        except OSError:
            pass
    if not row:
        row = models.AnswerSheetTemplate(paper_id=paper_id)
        db.add(row)
    row.file_path = None
    row.file_name = None
    row.file_type = "docx"
    row.file_size = 0
    row.source = "auto"
    db.commit()
    db.refresh(row)
    logger.info("sheet_template_reset", extra={"paper_id": paper_id})
    return {"code": 0, "message": "已恢复系统默认模板，下次下载将自动生成", "data": PaperTemplateOut.model_validate(row)}
