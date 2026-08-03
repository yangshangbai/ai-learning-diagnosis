"""Student and StudentSnapshot models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"))
    mastery = Column(Integer, default=50)  # 0-100
    trend = Column(String(20), default="stable")  # up / down / stable
    weak_points = Column(Text, default="[]")  # JSON array
    avatar_color = Column(String(10), default="#4F46E5")
    report_json = Column(Text, default="")  # JSON string: teacher report data
    created_at = Column(DateTime, default=datetime.utcnow)

    class_ = relationship("Class", back_populates="students")
    snapshots = relationship("StudentSnapshot", back_populates="student")
    question_results = relationship("QuestionResult", back_populates="student")
    exercise_plans = relationship("ExercisePlan", back_populates="student_ref")

    def __repr__(self):
        return f"<Student(id={self.id}, name='{self.name}', mastery={self.mastery})>"


class StudentSnapshot(Base):
    __tablename__ = "student_snapshots"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    snapshot_date = Column(Date)
    kp_mastery_json = Column(Text, default="{}")  # JSON dict
    ability_radar_json = Column(Text, default="{}")  # JSON dict
    error_causes_json = Column(Text, default="[]")  # JSON array
    trend = Column(String(20), default="stable")
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student", back_populates="snapshots")

    def __repr__(self):
        return f"<StudentSnapshot(id={self.id}, student_id={self.student_id})>"
