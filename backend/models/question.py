"""Question, QuestionSource, and SourceOperation models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from database import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    type = Column(String(30))  # 计算题 / 应用题 / 解答题 / 填空题 / 纠错题 / 开放题
    subject = Column(String(20))
    grade = Column(String(20))
    difficulty = Column(Integer, default=2)  # 1-3 (基础/中等/拔高)
    kp_name = Column(String(100))  # 主知识点名称
    kp_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=True)
    source = Column(String(50), default="本地题库")  # 本地题库 / 教研云
    external_id = Column(String(50), default="")
    sync_status = Column(String(20), default="")  # 已同步 / 待处理等
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Question(id={self.id}, kp='{self.kp_name}', source='{self.source}')>"


class QuestionSource(Base):
    __tablename__ = "question_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(50))  # 教研云
    status = Column(String(20), default="running")
    priority = Column(String(30), default="external_first")
    schedule = Column(String(30), default="每日 02:00")
    min_pool = Column(Integer, default=30)
    last_sync = Column(String(30), default="")
    mapping_coverage = Column(Integer, default=96)
    quality_pass_rate = Column(Integer, default=94)
    on_demand = Column(Boolean, default=True)
    scheduled_sync = Column(Boolean, default=True)
    fallback = Column(Boolean, default=True)

    def __repr__(self):
        return f"<QuestionSource(id={self.id}, name='{self.name}')>"


class SourceOperation(Base):
    __tablename__ = "source_operations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("question_sources.id"))
    time = Column(String(30))
    type = Column(String(30))
    detail = Column(Text)
    status = Column(String(20))

    def __repr__(self):
        return f"<SourceOperation(id={self.id}, type='{self.type}', status='{self.status}')>"
