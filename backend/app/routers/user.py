"""用户管理接口：对齐 Demo 用户列表。

端点：
  GET    /api/v1/users          列表（仅管理员 / 具备 user.view 权限）
  POST   /api/v1/users          新建（sha256 密码哈希；默认权限由角色决定）
  PUT    /api/v1/users/{id}     更新（含密码可选修改、permissions 模块权限勾选）
  DELETE /api/v1/users/{id}     软删除（is_active=False）

权限：user 模块属于敏感模块，读写均校验 require_permission("user", ...)；admin 直接放行。
"""
import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import models
from ..core.db import SessionLocal
from ..core.errors import NotFoundError, ConflictError, ValidationError
from ..core.logging import logger
from ..core.security import (
    Principal,
    default_teacher_permissions,
    permissions_view_for,
    require_permission,
)
from ..schemas.user import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/v1/users", tags=["user"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _resolve_permissions(role: str, permissions) -> Optional[dict]:
    """按角色解析落库 permissions：admin 恒为 None（全量放行）；非 admin 缺省给默认权限。"""
    if role == "admin":
        return None
    return permissions if permissions is not None else default_teacher_permissions()


def _to_out(u: models.User) -> UserOut:
    out = UserOut.model_validate(u)
    out.status = "active" if u.is_active else "disabled"
    out.permissions = permissions_view_for(u)
    return out


@router.get("")
def list_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    _: Principal = Depends(require_permission("user", "view")),
    db: Session = Depends(get_db),
):
    query = db.query(models.User)
    if role:
        query = query.filter(models.User.role == role)
    if status:
        # status: active / disabled → is_active
        query = query.filter(models.User.is_active == (status == "active"))
    total = query.count()
    rows = (
        query.order_by(desc(models.User.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": u.id,
            "username": u.username,
            "name": u.name or u.username,
            "role": u.role,
            "status": "active" if u.is_active else "disabled",
            "permissions": permissions_view_for(u),
            "last_login": None,  # User 模型无 last_login 字段，前端桥接处理
        }
        for u in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    _: Principal = Depends(require_permission("user", "add")),
    db: Session = Depends(get_db),
):
    exists = (
        db.query(models.User).filter(models.User.username == body.username).first()
    )
    if exists:
        raise ConflictError("用户名已存在")
    user = models.User(
        username=body.username,
        password_hash=_hash(body.password),
        name=body.name,
        role=body.role,
        permissions=_resolve_permissions(body.role, body.permissions),
        teacher_id=body.teacher_id,
        is_active=body.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(
        "user_created",
        extra={"id": user.id, "username": user.username, "role": user.role},
    )
    return _to_out(user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    _: Principal = Depends(require_permission("user", "edit")),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise NotFoundError("用户", user_id)
    data = body.model_dump(exclude_unset=True)
    # 密码单独处理（明文 → hash）
    if "password" in data:
        new_pw = data.pop("password")
        if new_pw:
            user.password_hash = _hash(new_pw)
    # 角色 + 权限联动：admin 恒全量；非 admin 显式传 permissions 则写入，否则补默认
    new_role = data.get("role", user.role)
    perm_passed = "permissions" in data
    raw_perms = data.pop("permissions") if perm_passed else None
    if new_role == "admin":
        user.permissions = None
    elif perm_passed:
        # 显式传 permissions：空 dict/null = 清零全部模块权限（BUG-L007：空字典曾被 or 兜底吞掉）
        user.permissions = raw_perms if raw_perms else {}
    elif user.permissions is None:
        user.permissions = default_teacher_permissions()
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    logger.info("user_updated", extra={"id": user.id, "fields": list(data.keys())})
    return _to_out(user)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    _: Principal = Depends(require_permission("user", "delete")),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise NotFoundError("用户", user_id)
    # 软删除：禁用账号，保留行用于审计
    user.is_active = False
    db.commit()
    logger.info("user_disabled", extra={"id": user_id})
    return {"code": 0, "message": "deleted", "data": None}
