"""QuestionResult model - AI diagnosis results for each question."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class QuestionResult(Base):
    __tablename__ = "question_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    student_id = Column(Integer, ForeignKey("students.id"))
    question_number = Column(Integer)
    verdict = Column(String(30))  # correct / incorrect / partially_correct / uncertain
    ocr_text = Column(Text, default="")
    wrong_step = Column(Text, default="")
    primary_kp_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=True)
    related_kps = Column(Text, default="[]")  # JSON array
    kp_name = Column(String(100))
    error_cause = Column(String(50), default="")  # K型错因
    skill_cause = Column(String(50), default="")  # S型错因
    ability_dimension = Column(String(50))
    ai_explain = Column(Text, default="")
    ai_confidence = Column(Float, default=0.0)
    ai_raw_json = Column(Text, default="{}")  # AI原始输出
    is_typical = Column(Boolean, default=False)
    teacher_verdict = Column(String(30), default="")
    teacher_note = Column(Text, default="")
    teacher_modified = Column(Boolean, default=False)
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="question_results")
    student = relationship("Student", back_populates="question_results")

    def __repr__(self):
        return f"<QuestionResult(id={self.id}, num={self.question_number}, verdict='{self.verdict}')>"
