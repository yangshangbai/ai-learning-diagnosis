"""教师 schemas。新建教师包含登录账号与初始密码。"""
from typing import Optional, List
from pydantic import Field, BaseModel, field_validator
from datetime import datetime


class TeacherClassItem(BaseModel):
    class_id: int
    role: str  # head_teacher / subject_teacher
    subject_id: Optional[int] = None


class TeacherCreate(BaseModel):
    name: str = Field(..., max_length=255)

    gender: Optional[str] = None
    phone: Optional[str] = None
    subject_ids: Optional[List[int]] = None
    remark: Optional[str] = None
    # 登录账号（必填）
    username: str
    password: str
    classes: Optional[List[TeacherClassItem]] = None

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if not v or not v.strip():
            raise ValueError("name 不能为空")
        return v.strip()

    @field_validator("username")
    @classmethod
    def _user(cls, v):
        if not v or not v.strip():
            raise ValueError("username 不能为空")
        return v.strip()

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        if not v or len(v) < 6:
            raise ValueError("密码至少 6 位")
        return v


class TeacherUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    subject_ids: Optional[List[int]] = None
    remark: Optional[str] = None
    status: Optional[str] = None


class TeacherOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    teacher_code: Optional[str] = None
    name: str
    gender: Optional[str] = None
    phone: Optional[str] = None
    subject_ids: Optional[List[int]] = None
    remark: Optional[str] = None
    status: str = "active"
    username: Optional[str] = None
    class_ids: List[int] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedTeacher(BaseModel):
    items: List[TeacherOut]
    total: int
    page: int
    page_size: int
