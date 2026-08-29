"""学生模型。

Student：student_code 系统生成（A01-Z99，不可手填，删除不回收，超限报错）。
StudentStatistic：学生全景看板（排名/进退步/知识点雷达/分数段/评价历史）。
"""
from datetime import datetime, timezone, date

from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Text, Date, Float

from ..core.db import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(8), nullable=True, unique=True, index=True)
    name = Column(String(64), nullable=False)
    gender = Column(String(8), nullable=True)  # male / female
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    birth_date = Column(Date, nullable=True)
    avatar = Column(String(255), nullable=True)
    parent_name = Column(String(64), nullable=True)
    parent_phone = Column(String(32), nullable=True)
    enrollment_date = Column(Date, nullable=True)
    initial_evaluation = Column(Text, nullable=True)
    remark = Column(Text, nullable=True)
    recent_evaluations = Column(JSON, nullable=True)  # 考后教师评价历史 [{id,task_code,task_name,date,score,full_score,evaluation,teacher,created_at}]
    status = Column(String(16), default="active")  # active / archived
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class StudentStatistic(Base):
    __tablename__ = "student_statistics"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, unique=True, index=True)
    exam_count = Column(Integer, default=0)
    expected_count = Column(Integer, default=0)
    participation_rate = Column(Float, nullable=True)
    avg_score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    min_score = Column(Float, nullable=True)
    last_exam_date = Column(Date, nullable=True)
    last_exam_score = Column(Float, nullable=True)
    class_rank = Column(Integer, nullable=True)
    rank_trend = Column(JSON, nullable=True)
    score_trend = Column(JSON, nullable=True)
    type_accuracy = Column(JSON, nullable=True)
    knowledge_mastery = Column(JSON, nullable=True)
    weak_knowledge = Column(JSON, nullable=True)
    strong_knowledge = Column(JSON, nullable=True)
    score_distribution = Column(JSON, nullable=True)
    improvement_status = Column(String(16), nullable=True)  # improving / declining / stable
    recent_evaluations = Column(JSON, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
