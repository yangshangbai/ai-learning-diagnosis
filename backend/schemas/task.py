"""Task schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, description="任务名称不能为空")
    type: str = "日常作业"
    subject: str = "数学"
    grade: str
    class_ids: List[int] = []
    pages: int = 4
    objective: str = ""
    kps: List[str] = []
    difficulty: str = "中等"


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    subject: Optional[str] = None
    grade: Optional[str] = None
    class_ids: Optional[List[int]] = None
    pages: Optional[int] = None
    objective: Optional[str] = None
    kps: Optional[List[str]] = None
    difficulty: Optional[str] = None
    status: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str  # draft/pending_upload/ai_processing/pending_review/completed


class TaskOut(BaseModel):
    id: int
    name: str
    type: str
    subject: str
    grade: str
    difficulty: str
    pages: int
    objective: str
    status: str
    kps: list = []
    class_ids: list = []
    class_names: str = ""
    confirmed_count: int = 0
    total_count: int = 0
    creator_name: str = ""
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
