"""Student schemas."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class StudentCreate(BaseModel):
    name: str
    class_id: int
    mastery: int = 50
    trend: str = "stable"
    weak_points: List[str] = []
    avatar_color: str = "#4F46E5"


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    class_id: Optional[int] = None
    mastery: Optional[int] = None
    trend: Optional[str] = None
    weak_points: Optional[List[str]] = None
    avatar_color: Optional[str] = None


class StudentOut(BaseModel):
    id: int
    name: str
    class_id: int
    class_name: str = ""
    grade: str = ""
    mastery: int
    trend: str
    weak_points: list = []
    avatar_color: str = ""
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
