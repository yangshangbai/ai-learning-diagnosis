"""学生 schemas。"""
from typing import Optional, List
from pydantic import BaseModel, field_validator
from datetime import datetime, date


class StudentCreate(BaseModel):
    name: str
    class_id: int
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    avatar: Optional[str] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    enrollment_date: Optional[date] = None
    initial_evaluation: Optional[str] = None
    remark: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if not v or not v.strip():
            raise ValueError("name 不能为空")
        return v.strip()


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    class_id: Optional[int] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    avatar: Optional[str] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    enrollment_date: Optional[date] = None
    initial_evaluation: Optional[str] = None
    remark: Optional[str] = None
    status: Optional[str] = None
    recent_evaluations: Optional[list] = None


class StudentOut(BaseModel):
    id: int
    student_code: Optional[str] = None
    name: str
    gender: Optional[str] = None
    class_id: int
    class_name: Optional[str] = None
    birth_date: Optional[date] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    enrollment_date: Optional[date] = None
    initial_evaluation: Optional[str] = None
    remark: Optional[str] = None
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    recent_evaluations: Optional[list] = None

    model_config = {"from_attributes": True}


class PaginatedStudent(BaseModel):
    items: List[StudentOut]
    total: int
    page: int
    page_size: int


class StudentDashboard(BaseModel):
    student_id: int
    exam_count: int = 0
    expected_count: int = 0
    participation_rate: Optional[float] = None
    avg_score: Optional[float] = None
    max_score: Optional[float] = None
    min_score: Optional[float] = None
    class_rank: Optional[int] = None
    rank_trend: Optional[list] = None
    score_trend: Optional[list] = None
    type_accuracy: Optional[list] = None
    knowledge_mastery: Optional[list] = None
    weak_knowledge: Optional[list] = None
    strong_knowledge: Optional[list] = None
    score_distribution: Optional[list] = None
    improvement_status: Optional[str] = None
    recent_evaluations: Optional[list] = None

    model_config = {"from_attributes": True}


class EvaluationCreate(BaseModel):
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    date: Optional[str] = None
    score: Optional[float] = None
    full_score: Optional[float] = None
    evaluation: str
    teacher: Optional[str] = None
