"""Class and Grade schemas."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class GradeOut(BaseModel):
    id: int
    name: str
    sort_order: int

    class Config:
        from_attributes = True


class ClassCreate(BaseModel):
    name: str
    grade_id: int
    subjects: List[str] = []


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    grade_id: Optional[int] = None
    subjects: Optional[List[str]] = None


class ClassOut(BaseModel):
    id: int
    name: str
    grade_id: int
    grade_name: str = ""
    subjects: list = []
    student_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GradeCreate(BaseModel):
    name: str
    sort_order: int = 0


class GradeUpdate(BaseModel):
    name: Optional[str] = None
    sort_order: Optional[int] = None
