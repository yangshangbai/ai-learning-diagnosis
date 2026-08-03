"""Grade and Class models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Grade(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True)
    name = Column(String(20), nullable=False)  # 五年级 / 六年级 / 初一 / 初二 / 初三
    sort_order = Column(Integer, default=0)

    classes = relationship("Class", back_populates="grade")

    def __repr__(self):
        return f"<Grade(id={self.id}, name='{self.name}')>"


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)  # 五(1)班
    grade_id = Column(Integer, ForeignKey("grades.id"), nullable=False)
    subjects = Column(Text, default="[]")  # JSON array
    created_at = Column(DateTime, default=datetime.utcnow)

    grade = relationship("Grade", back_populates="classes")
    students = relationship("Student", back_populates="class_")
    teacher_links = relationship("TeacherClass", back_populates="class_")

    def __repr__(self):
        return f"<Class(id={self.id}, name='{self.name}')>"
