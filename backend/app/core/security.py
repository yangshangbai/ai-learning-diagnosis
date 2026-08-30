"""鉴权：JWT（python-jose）+ 模块权限（RBAC 升级版）。

权限模型（需求调整）：
- 角色仅保留「管理员 admin」；业务权限改为按模块勾选。
- 每个业务模块固定 4 个动作：view / add / edit / delete。
- 管理员（role == "admin"）默认放行所有模块与动作。
- 非管理员用户的权限存 users.permissions（JSON：{module: [action,...]}）。
- get_current_user 解析 token 后回查数据库刷新权限/角色，管理员改权限后立即生效。

兼容说明：
- access token 负载仅含最小声明：user_id / role / name / teacher_id，不含 permissions。
- 原 role 字段保留返回（前端兼容），新增 permissions 字段。
"""
from datetime import datetime, timedelta, timezone

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import settings
from .errors import AuthError, ForbiddenError

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# 模块权限常量（与前端菜单一一对应，key 由本模块统一出口）
# ---------------------------------------------------------------------------
# 业务模块 key 清单：题库/试卷/考试任务/学生/班级/教师/用户管理/AI评分/AI选题/教研云同步/系统设置
MODULE_KEYS = [
    "question",     # 题库
    "paper",        # 试卷
    "exam",         # 考试任务
    "student",      # 学生
    "class",        # 班级
    "teacher",      # 教师
    "user",         # 用户管理
    "ai",           # AI 评分
    "ai_select",    # AI 选题
    "sync",         # 教研云同步（docx 导入/导出、导入日志）
    "system",       # 系统设置（基础分类/标签/系统日志）
]

ALL_ACTIONS = ["view", "add", "edit", "delete"]

# 敏感模块：默认不给非管理员（用户管理 / 系统设置）
SENSITIVE_MODULES = {"user", "system"}


def all_permissions() -> dict:
    """所有模块的全量权限结构（管理员与前端「权限勾选」面板用）。"""
    return {m: list(ALL_ACTIONS) for m in MODULE_KEYS}


def default_teacher_permissions() -> dict:
    """非管理员默认迁移权限：除敏感模块外的所有模块 view+add+edit（不含 delete）。"""
    return {
        m: [a for a in ALL_ACTIONS if a != "delete"]
        for m in MODULE_KEYS
        if m not in SENSITIVE_MODULES
    }


def permissions_view_for(user) -> dict:
    """将 User ORM 行转换为前端可用的权限结构。

    - admin：返回全模块全动作（前端展示为全选，且不落库）
    - 非 admin：如实返回已配置权限（{} = 已显式清零，与 require_permission 执行一致，BUG-L008）
    """
    if getattr(user, "role", None) == "admin":
        return all_permissions()
    return user.permissions or {}


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(
    user_id: int, role: str, username: str, teacher_id: int | None = None
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "role": role,
        "name": username,
        "teacher_id": teacher_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


class Principal:
    def __init__(self, user_id, role, name, teacher_id=None, permissions=None):
        self.user_id = user_id
        self.role = role
        self.name = name
        self.teacher_id = teacher_id
        # {module: [action,...]}；admin 可为 None/{}（require_permission 对 admin 直接放行）
        self.permissions = permissions

    def has_permission(self, module: str, action: str) -> bool:
        """admin 全放行；非 admin 按 permissions 判定。"""
        if self.role == "admin":
            return True
        actions = (self.permissions or {}).get(module) or []
        return action in actions


def _load_principal_from_db(user_id: int) -> "Principal | None":
    """按 user_id 回查数据库构造 Principal，保证权限/禁用状态即时生效。

    用户不存在或已禁用返回 None（等价未登录）。
    """
    from ..core.db import SessionLocal
    from .. import models

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user is None or not user.is_active:
            return None
        return Principal(
            user_id=user.id,
            role=user.role,
            name=user.name or user.username,
            teacher_id=user.teacher_id,
            permissions=user.permissions,
        )
    finally:
        db.close()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal | None:
    """返回 None 表示未登录（用于「前端错误上报」允许匿名上报的场景）。"""
    if not creds or not creds.credentials:
        return None
    try:
        data = decode_token(creds.credentials)
    except JWTError:
        return None
    uid = data.get("user_id")
    if uid is None:
        return None
    return _load_principal_from_db(uid)


def require_auth(principal: Principal | None = Depends(get_current_user)) -> Principal:
    if principal is None:
        raise AuthError()
    return principal


def require_admin(principal: Principal | None = Depends(get_current_user)) -> Principal:
    if principal is None:
        raise AuthError()
    if principal.role != "admin":
        raise ForbiddenError("仅管理员可访问")
    return principal


def require_permission(module: str, action: str):
    """模块权限依赖工厂。

    用法：
        _: Principal = Depends(require_permission("question", "add"))
    admin 直接放行；非 admin 校验 permissions[module] 是否含 action，否则 403。
    """

    def _dep(principal: Principal | None = Depends(get_current_user)) -> Principal:
        if principal is None:
            raise AuthError()
        if not principal.has_permission(module, action):
            raise ForbiddenError(f"无权执行该操作（模块 {module} · {action}）")
        return principal

    return _dep
