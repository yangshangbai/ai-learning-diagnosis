"""标签模型。

Tag：全局标签列表（对应前端「标签管理」页）。
Question.tags 为 JSON 数组，存 Tag.id 列表。
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime

from ..core.db import Base


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False, unique=True, index=True)
    color = Column(String(16), default="blue")  # red / blue / orange / green
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
