"""KnowledgePoint schemas."""

from __future__ import annotations

from pydantic import BaseModel
from typing import Optional, List


class KPCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    subject: str = ""
    grade: str = ""
    stage: str = ""
    level: int = 1
    keywords: List[str] = []
    sort_order: int = 0


class KPUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    subject: Optional[str] = None
    grade: Optional[str] = None
    stage: Optional[str] = None
    keywords: Optional[List[str]] = None
    sort_order: Optional[int] = None
    mastery: Optional[float] = None


class KPOut(BaseModel):
    id: int
    parent_id: Optional[int] = None
    name: str
    subject: str
    grade: str
    stage: str
    level: int
    keywords: list = []
    sort_order: int
    mastery: float = 0.0
    children: List[KPOut] = []

    class Config:
        from_attributes = True
