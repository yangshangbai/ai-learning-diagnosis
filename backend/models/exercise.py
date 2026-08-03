"""ExercisePlan model - personalized exercise plans."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class ExercisePlan(Base):
    __tablename__ = "exercise_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    student_name = Column(String(50))
    target_kp = Column(String(200))
    frequency = Column(String(20))  # 每天1次 / 每周3次 / 每周1次
    question_count = Column(Integer, default=10)
    difficulty = Column(String(20), default="中等")
    source = Column(String(100), default="统一智能题库")
    source_trace = Column(String(200), default="")
    status = Column(String(20), default="进行中")
    effect = Column(String(20), default="待观察")
    created_at = Column(DateTime, default=datetime.utcnow)

    student_ref = relationship("Student", back_populates="exercise_plans")

    def __repr__(self):
        return f"<ExercisePlan(id={self.id}, student='{self.student_name}', target='{self.target_kp}')>"
