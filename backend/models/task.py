"""Task and TaskClass models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    type = Column(String(50))  # 周测 / 日常作业 / 专项练习 / 阶段测 / 期末模拟
    subject = Column(String(20))
    grade = Column(String(20))  # 五年级 - 初三
    difficulty = Column(String(20), default="中等")
    pages = Column(Integer, default=4)
    objective = Column(Text, default="")
    status = Column(String(30), default="draft")
    # draft -> pending_upload -> ai_processing -> pending_review -> completed
    kps = Column(Text, default="[]")  # JSON array
    confirmed_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    class_ids = Column(Text, default="[]")  # JSON array of class IDs

    creator = relationship("User")
    question_results = relationship("QuestionResult", back_populates="task")

    def __repr__(self):
        return f"<Task(id={self.id}, name='{self.name}', status='{self.status}')>"


class TaskClass(Base):
    __tablename__ = "task_classes"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    class_id = Column(Integer, ForeignKey("classes.id"))

    def __repr__(self):
        return f"<TaskClass(task_id={self.task_id}, class_id={self.class_id})>"
