"""鉴权桩（dev 自测用）。

生产对接 Demo 已确认的 RBAC：
- 登录校验走 users 表（密码 sha256，生产应换 bcrypt/argon2）。
- 返回 JWT；前端内存持有 access token，刷新逻辑后续补充。
- 仅管理员角色可访问系统日志等敏感接口。
"""
import hashlib

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..core.db import SessionLocal
from ..core.errors import AuthError
from ..core.security import (
    Principal,
    all_permissions,
    create_access_token,
    get_current_user,
    permissions_view_for,
)
from .. import models

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


@router.post("/login")
def login(body: LoginIn):
    db = SessionLocal()
    try:
        user = (
            db.query(models.User).filter(models.User.username == body.username).first()
        )
        if not user or user.password_hash != _hash(body.password) or not user.is_active:
            raise AuthError("用户名或密码错误")
        token = create_access_token(user.id, user.role, user.name or user.username, user.teacher_id)
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": user.role,
            "name": user.name or user.username,
            "user_id": user.id,
            "teacher_id": user.teacher_id,
            # 模块权限：供前端控制菜单/按钮显隐
            "permissions": permissions_view_for(user),
            "all_permissions": all_permissions(),
        }
    finally:
        db.close()


@router.get("/me")
def me(principal: Principal | None = Depends(get_current_user)):
    if principal is None:
        raise AuthError()
    # Principal 已由 get_current_user 回查数据库，permissions 为最新值
    perms = (
        all_permissions()
        if principal.role == "admin"
        else (principal.permissions or all_permissions())
    )
    return {
        "user_id": principal.user_id,
        "role": principal.role,
        "name": principal.name,
        "teacher_id": principal.teacher_id,
        "permissions": perms,
        "all_permissions": all_permissions(),
    }
