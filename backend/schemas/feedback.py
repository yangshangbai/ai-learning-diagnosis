"""Feedback schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class FeedbackCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=20)
    content: str = Field(..., min_length=1, max_length=200)
    images: List[str] = []


class FeedbackUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=20)
    content: Optional[str] = Field(None, min_length=1, max_length=200)
    images: Optional[List[str]] = None


class FeedbackOut(BaseModel):
    id: int
    user_id: int
    username: str
    title: str
    content: str
    images: List[str]
    status: str
    submitted_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FeedbackListOut(BaseModel):
    items: List[FeedbackOut]
    total: int
    page: int
    page_size: int
