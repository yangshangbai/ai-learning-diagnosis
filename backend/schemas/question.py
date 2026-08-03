"""Question and QuestionSource schemas."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class QuestionCreate(BaseModel):
    title: str
    type: str
    subject: str
    grade: str
    difficulty: int = 2
    kp_id: Optional[int] = None
    kp_name: str = ""
    source: str = "本地题库"
    external_id: str = ""


class QuestionUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    subject: Optional[str] = None
    grade: Optional[str] = None
    difficulty: Optional[int] = None
    kp_id: Optional[int] = None
    kp_name: Optional[str] = None
    source: Optional[str] = None
    external_id: Optional[str] = None
    sync_status: Optional[str] = None
    usage_count: Optional[int] = None


class QuestionOut(BaseModel):
    id: int
    title: str
    type: str
    subject: str
    grade: str
    difficulty: int
    kp_name: str
    kp_id: Optional[int] = None
    source: str
    external_id: str
    sync_status: str
    usage_count: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SourcePolicyUpdate(BaseModel):
    priority: Optional[str] = None
    schedule: Optional[str] = None
    min_pool: Optional[int] = None
    on_demand: Optional[bool] = None
    scheduled_sync: Optional[bool] = None
    fallback: Optional[bool] = None
