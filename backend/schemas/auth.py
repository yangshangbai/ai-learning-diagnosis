"""Authentication schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List


class LoginRequest(BaseModel):
    phone: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict  # {id, name, role, phone, avatar, grades, subjects}


class UserInfo(BaseModel):
    id: int
    name: str
    phone: str
    role: str
    avatar: str = ""
    grades: list = []
    subjects: list = []

    class Config:
        from_attributes = True


class TeacherCreate(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str
    password: str
    role: str = "teacher"
    grades: List[str] = []
    subjects: List[str] = []
    class_ids: List[int] = []


class TeacherUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    grades: Optional[List[str]] = None
    subjects: Optional[List[str]] = None
    class_ids: Optional[List[int]] = None
