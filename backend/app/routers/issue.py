"""问题需求（Case）接口：提交/列表/详情/编辑/状态流转/删除 + 图片上传。

端点（登录即可查看与提交；状态流转限管理员；删除限管理员或创建人本人且待处理）：
  POST   /api/v1/issues                    提交问题需求 {title, module, description, images}
  GET    /api/v1/issues                    列表 ?page&page_size&status&module&keyword
  GET    /api/v1/issues/{id}               详情
  PATCH  /api/v1/issues/{id}               编辑内容（创建人·待处理 或 admin）/ 状态流转（admin）
  DELETE /api/v1/issues/{id}               删除
  POST   /api/v1/issues/upload-image       上传图片 → {url:"/uploads/issues/xxx.png"}
"""
import datetime
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, field_validator
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.errors import ForbiddenError, NotFoundError, ValidationError
from ..core.logging import logger
from ..core.security import Principal, require_admin, require_auth

router = APIRouter(prefix="/api/v1/issues", tags=["issues"])

# 图片落盘目录：优先环境变量 UPLOAD_DIR（云端=/opt/ai-learning/uploads，nginx /uploads/ 静态映射）
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ISSUE_IMG_DIR = os.path.join(
    os.getenv("UPLOAD_DIR") or os.path.join(_ROOT, "uploads"), "issues"
)
_IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_IMG_MAX_SIZE = 10 * 1024 * 1024          # 单图 ≤10MB
_IMG_MAGIC = {b"\x89PNG\r\n\x1a\n": ".png", b"\xff\xd8\xff": ".jpg"}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


VALID_MODULES = ["题库管理", "试卷管理", "考试任务", "学生管理", "班级管理",
                 "教师管理", "AI评分", "AI选题", "系统设置", "其他"]
VALID_STATUS = [models.Issue.STATUS_PENDING, models.Issue.STATUS_PROCESSING, models.Issue.STATUS_DONE]


class IssueCreateBody(BaseModel):
    title: str
    module: str = "其他"
    description: str = ""
    images: list[str] = []

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("标题不能为空")
        if len(v) > 200:
            raise ValueError("标题不能超过 200 字")
        return v

    @field_validator("module")
    @classmethod
    def _module(cls, v: str) -> str:
        v = (v or "").strip() or "其他"
        if v not in VALID_MODULES:
            raise ValueError(f"不支持的问题模块：{v}")
        return v

    @field_validator("description")
    @classmethod
    def _desc(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) > 500:
            raise ValueError("说明内容不能超过 500 字")
        return v

    @field_validator("images")
    @classmethod
    def _images(cls, v: list) -> list:
        out = []
        for u in (v or [])[:9]:          # 最多 9 张
            u = str(u or "").strip()
            if u.startswith("/uploads/issues/") and ".." not in u and u not in out:
                out.append(u)
        return out


class IssuePatchBody(BaseModel):
    title: str | None = None
    module: str | None = None
    description: str | None = None
    images: list[str] | None = None
    status: str | None = None


def _gen_case_no(db: Session) -> str:
    """C + YYYYMMDD + 3位当日流水（含并发重试）。"""
    today = datetime.date.today().strftime("%Y%m%d")
    prefix = f"C{today}"
    n = db.query(models.Issue).filter(models.Issue.case_no.like(prefix + "%")).count()
    for i in range(n + 1, n + 100):
        case_no = f"{prefix}{i:03d}"
        if not db.query(models.Issue.id).filter(models.Issue.case_no == case_no).first():
            return case_no
    raise ValidationError("Case 编号生成失败，请重试")


def _out(i: models.Issue) -> dict:
    return {
        "id": i.id,
        "case_no": i.case_no,
        "title": i.title,
        "module": i.module,
        "description": i.description or "",
        "images": i.images or [],
        "status": i.status,
        "created_by": i.created_by,
        "created_by_name": i.created_by_name,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "completed_at": i.completed_at.isoformat() if i.completed_at else None,
    }


@router.post("")
def create_issue(body: IssueCreateBody, principal: Principal = Depends(require_auth), db: Session = Depends(get_db)):
    issue = models.Issue(
        case_no=_gen_case_no(db),
        title=body.title,
        module=body.module,
        description=body.description,
        images=body.images or [],
        status=models.Issue.STATUS_PENDING,
        created_by=principal.user_id,
        created_by_name=principal.name,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    logger.info("issue_created", extra={"case_no": issue.case_no, "user": principal.user_id})
    return {"code": 0, "message": "created", "data": _out(issue)}


@router.get("")
def list_issues(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str = Query(""),
    module: str = Query(""),
    keyword: str = Query(""),
    _: Principal = Depends(require_auth),
    db: Session = Depends(get_db),
):
    q = db.query(models.Issue)
    if status:
        q = q.filter(models.Issue.status == status)
    if module:
        q = q.filter(models.Issue.module == module)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(or_(models.Issue.title.ilike(kw), models.Issue.description.ilike(kw),
                         models.Issue.case_no.ilike(kw)))
    total = q.count()
    rows = (
        q.order_by(desc(models.Issue.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"code": 0, "message": "ok", "data": {
        "items": [_out(i) for i in rows], "total": total, "page": page, "page_size": page_size
    }}


@router.get("/upload-image")
def upload_hint():
    raise ValidationError("请用 POST multipart/form-data 上传图片（字段名 file）")


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), _: Principal = Depends(require_auth)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _IMG_EXT:
        raise ValidationError("仅支持 png / jpg / jpeg / webp 图片")
    data = await file.read()
    if not data:
        raise ValidationError("上传文件为空")
    if len(data) > _IMG_MAX_SIZE:
        raise ValidationError("单张图片不能超过 10MB")
    # 内容嗅探：伪装扩展名拦截（按文件头魔数判定 png/jpg；其余按原扩展存 webp）
    magic_ext = None
    for magic, e in _IMG_MAGIC.items():
        if data.startswith(magic):
            magic_ext = e
            break
    if magic_ext is None and ext != ".webp":
        raise ValidationError("文件内容不是有效图片")
    if magic_ext:
        ext = magic_ext

    os.makedirs(ISSUE_IMG_DIR, exist_ok=True)
    fname = f"issue_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    with open(os.path.join(ISSUE_IMG_DIR, fname), "wb") as f:
        f.write(data)
    url = f"/uploads/issues/{fname}"
    logger.info("issue_image_uploaded", extra={"file": fname, "size": len(data)})
    return {"code": 0, "message": "ok", "data": {"url": url}}


@router.get("/{issue_id}")
def get_issue(issue_id: int, _: Principal = Depends(require_auth), db: Session = Depends(get_db)):
    i = db.query(models.Issue).filter(models.Issue.id == issue_id).first()
    if not i:
        raise NotFoundError("问题需求", issue_id)
    return {"code": 0, "message": "ok", "data": _out(i)}


@router.patch("/{issue_id}")
def patch_issue(issue_id: int, body: IssuePatchBody, principal: Principal = Depends(require_auth),
                db: Session = Depends(get_db)):
    i = db.query(models.Issue).filter(models.Issue.id == issue_id).first()
    if not i:
        raise NotFoundError("问题需求", issue_id)
    is_admin = principal.role == "admin"
    is_owner = i.created_by == principal.user_id

    # 内容编辑：创建人（仅待处理）或 admin
    content_fields = body.title is not None or body.module is not None or \
        body.description is not None or body.images is not None
    if content_fields:
        if not (is_admin or (is_owner and i.status == models.Issue.STATUS_PENDING)):
            raise ForbiddenError("仅创建人可在「待处理」时编辑内容，或由管理员修改")
        if body.title is not None:
            i.title = IssueCreateBody(title=body.title).title
        if body.module is not None:
            i.module = IssueCreateBody(module=body.module).module
        if body.description is not None:
            i.description = IssueCreateBody(description=body.description).description
        if body.images is not None:
            i.images = IssueCreateBody(images=body.images).images

    # 状态流转：仅 admin
    if body.status is not None:
        if not is_admin:
            raise ForbiddenError("状态流转仅管理员可操作")
        if body.status not in VALID_STATUS:
            raise ValidationError(f"不支持的状态：{body.status}")
        i.status = body.status
        if body.status == models.Issue.STATUS_DONE and not i.completed_at:
            i.completed_at = datetime.datetime.now(datetime.timezone.utc)
        elif body.status != models.Issue.STATUS_DONE:
            i.completed_at = None

    db.commit()
    db.refresh(i)
    return {"code": 0, "message": "updated", "data": _out(i)}


@router.delete("/{issue_id}")
def delete_issue(issue_id: int, principal: Principal = Depends(require_auth), db: Session = Depends(get_db)):
    i = db.query(models.Issue).filter(models.Issue.id == issue_id).first()
    if not i:
        raise NotFoundError("问题需求", issue_id)
    is_admin = principal.role == "admin"
    is_owner_pending = i.created_by == principal.user_id and i.status == models.Issue.STATUS_PENDING
    if not (is_admin or is_owner_pending):
        raise ForbiddenError("仅管理员可删除，或创建人删除本人「待处理」的需求")
    db.delete(i)
    db.commit()
    return {"code": 0, "message": "deleted"}
