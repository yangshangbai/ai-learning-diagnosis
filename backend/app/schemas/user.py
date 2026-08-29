"""用户 schemas：管理员后台 CRUD 用。

与 auth.py 的 LoginIn 区分：此处用于后台管理新建/编辑用户。
密码使用 sha256（与 auth.py 一致），仅写入 password_hash，不回传。
permissions：模块权限 {module: [action,...]}。不传则由服务端按角色给默认值。
"""
from typing import Optional, Dict, List
from datetime import datetime

from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    username: str
    password: str
    name: Optional[str] = None
    role: str = "teacher"  # admin / teacher
    is_active: bool = True
    teacher_id: Optional[int] = None
    permissions: Optional[Dict[str, List[str]]] = None

    @field_validator("username")
    @classmethod
    def _check_user(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("username 不能为空")
        return v.strip()

    @field_validator("password")
    @classmethod
    def _check_pw(cls, v: str) -> str:
        if not v or len(v) < 6:
            raise ValueError("密码至少 6 位")
        return v

    @field_validator("role")
    @classmethod
    def _check_role(cls, v: str) -> str:
        if v not in ("admin", "teacher"):
            raise ValueError("role 必须是 admin 或 teacher")
        return v


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None  # 提供则修改密码
    teacher_id: Optional[int] = None
    permissions: Optional[Dict[str, List[str]]] = None

    @field_validator("role")
    @classmethod
    def _check_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("admin", "teacher"):
            raise ValueError("role 必须是 admin 或 teacher")
        return v

    @field_validator("password")
    @classmethod
    def _check_pw(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 6:
            raise ValueError("密码至少 6 位")
        return v


class UserOut(BaseModel):
    id: int
    username: str
    name: Optional[str] = None
    role: str
    teacher_id: Optional[int] = None
    is_active: bool
    permissions: Optional[dict] = None
    created_at: Optional[datetime] = None
    status: str = "active"  # 桥接前端 status 字段

    model_config = {"from_attributes": True}
