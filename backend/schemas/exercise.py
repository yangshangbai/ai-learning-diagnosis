"""ExercisePlan schemas."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ExerciseCreate(BaseModel):
    student_id: int
    target_kp: str
    frequency: str = "每周3次"
    question_count: int = 10
    difficulty: str = "中等"


class ExerciseUpdate(BaseModel):
    student_id: Optional[int] = None
    target_kp: Optional[str] = None
    frequency: Optional[str] = None
    question_count: Optional[int] = None
    difficulty: Optional[str] = None
    status: Optional[str] = None
    effect: Optional[str] = None
    source: Optional[str] = None
    source_trace: Optional[str] = None


class ExerciseOut(BaseModel):
    id: int
    student_id: int
    student_name: str
    target_kp: str
    frequency: str
    question_count: int
    difficulty: str
    source: str = ""
    source_trace: str = ""
    status: str
    effect: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
