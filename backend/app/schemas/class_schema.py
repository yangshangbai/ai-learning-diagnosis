"""班级 schemas。"""
from typing import Optional, List
from pydantic import Field, BaseModel, field_validator
from datetime import datetime


class ClassCreate(BaseModel):
    name: str = Field(..., max_length=255)

    stage: str  # primary / middle / high
    remark: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if not v or not v.strip():
            raise ValueError("name 不能为空")
        return v.strip()

    @field_validator("stage")
    @classmethod
    def _stage(cls, v):
        if v not in ("primary", "middle", "high"):
            raise ValueError("stage 必须是 primary/middle/high")
        return v


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    stage: Optional[str] = None
    remark: Optional[str] = None
    status: Optional[str] = None


class ClassOut(BaseModel):
    id: int
    class_code: Optional[str] = None
    name: str
    stage: str
    remark: Optional[str] = None
    status: str = "active"
    student_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedClass(BaseModel):
    items: List[ClassOut]
    total: int
    page: int
    page_size: int


class ClassDashboard(BaseModel):
    class_id: int
    student_count: int = 0
    exam_count: int = 0
    avg_score: Optional[float] = None
    pass_rate: Optional[float] = None
    excellent_rate: Optional[float] = None
    score_trend: Optional[list] = None
    score_distribution: Optional[list] = None
    ability_groups: Optional[list] = None
    knowledge_mastery: Optional[list] = None
    type_performance: Optional[list] = None
    difficulty_performance: Optional[list] = None
    improvement_list: Optional[list] = None
    decline_list: Optional[list] = None
    top_students: Optional[list] = None
    bottom_students: Optional[list] = None

    model_config = {"from_attributes": True}
