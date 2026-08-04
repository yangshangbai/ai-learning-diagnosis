"""Feedback / Bug report model."""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from datetime import datetime
from database import Base


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(50), nullable=False)
    title = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    images = Column(JSON, default=list)          # ["path1.jpg", "path2.png"]
    status = Column(String(20), default="已提交")  # 已提交 / 已受理 / 已完成
    submitted_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
