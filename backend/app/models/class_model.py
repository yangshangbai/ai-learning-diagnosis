"""班级模型。

Class：class_code 系统生成（小学 A / 初中 B / 高中 C，各 01-99）。
ClassStatistic：班级全景看板（分数分布/能力分组/知识点/题型/进退步/排行榜）。
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Text, Float

from ..core.db import Base


STAGE_PRIMARY = "primary"
STAGE_MIDDLE = "middle"
STAGE_HIGH = "high"
STAGE_MAP = {STAGE_PRIMARY: "A", STAGE_MIDDLE: "B", STAGE_HIGH: "C"}


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    class_code = Column(String(16), nullable=True, unique=True, index=True)
    name = Column(String(128), nullable=False)
    stage = Column(String(16), nullable=False)  # primary / middle / high
    remark = Column(Text, nullable=True)
    status = Column(String(16), default="active")  # active / archived
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ClassStatistic(Base):
    __tablename__ = "class_statistics"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, unique=True, index=True)
    student_count = Column(Integer, default=0)
    exam_count = Column(Integer, default=0)
    avg_score = Column(Float, nullable=True)
    pass_rate = Column(Float, nullable=True)
    excellent_rate = Column(Float, nullable=True)
    score_trend = Column(JSON, nullable=True)
    score_distribution = Column(JSON, nullable=True)
    ability_groups = Column(JSON, nullable=True)
    knowledge_mastery = Column(JSON, nullable=True)
    type_performance = Column(JSON, nullable=True)
    difficulty_performance = Column(JSON, nullable=True)
    improvement_list = Column(JSON, nullable=True)
    decline_list = Column(JSON, nullable=True)
    top_students = Column(JSON, nullable=True)
    bottom_students = Column(JSON, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
