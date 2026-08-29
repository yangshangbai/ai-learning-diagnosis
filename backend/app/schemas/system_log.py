"""Pydantic Schema：前后端字段对齐，后端做边界校验。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SystemLogCreate(BaseModel):
    level: str = "ERROR"
    source: str = "frontend"
    module: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=4000)
    detail: Optional[str] = None
    traceback: Optional[str] = None
    url: Optional[str] = Field(None, max_length=500)
    request_id: Optional[str] = Field(None, max_length=50)


class SystemLogOut(BaseModel):
    id: int
    level: str
    source: str
    module: Optional[str]
    message: str
    detail: Optional[str]
    traceback: Optional[str]
    url: Optional[str]
    user_id: Optional[int]
    username: Optional[str]
    request_id: Optional[str]
    created_at: Optional[datetime]
    repaired: bool
    repaired_at: Optional[datetime]
    repaired_by: Optional[int]
    repaired_note: Optional[str]

    model_config = {"from_attributes": True}


class SystemLogRepair(BaseModel):
    repaired: bool = True
    repaired_note: Optional[str] = Field(None, max_length=2000)


class PaginatedSystemLog(BaseModel):
    items: List[SystemLogOut]
    total: int
    page: int
    page_size: int
