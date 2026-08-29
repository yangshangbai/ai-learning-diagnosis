"""题库模型。

Question：question_code 位置编码（学科-年级-知识点-序号，如 MAT-G7-KP003-0027）。
QuestionImage：题目图片表。
ImportLog：导入日志表（去重覆盖统计）。
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Text

from ..core.db import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    question_code = Column(String(64), nullable=True, unique=True, index=True)
    source = Column(String(32), default="manual")  # manual / jiaoyanyun
    source_id = Column(String(64), nullable=True, index=True)  # 教研云题目 ID
    subject_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    grade_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    ques_type = Column(String(32), nullable=False)  # single_choice/multi_choice/fill_blank/true_false/essay
    difficulty = Column(Integer, default=1)  # 1-5
    stem = Column(Text, nullable=False)  # HTML 含公式/图片
    options = Column(JSON, nullable=True)  # 选择题选项
    answer = Column(Text, nullable=True)
    analysis = Column(Text, nullable=True)
    score = Column(Integer, default=0)
    knowledge_ids = Column(JSON, nullable=True)  # 知识点 category_id 数组
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)  # 题库分类
    tags = Column(JSON, nullable=True)  # 标签 id 数组（对应 tags 表）
    images = Column(JSON, nullable=True)
    status = Column(String(16), default="active")  # active / archived
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class QuestionImage(Base):
    __tablename__ = "question_images"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    url = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ImportLog(Base):
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(32), default="manual")
    total = Column(Integer, default=0)
    success = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    detail = Column(JSON, nullable=True)
    operator_id = Column(Integer, nullable=True)
    # Demo 对齐字段（additive，旧字段保留兼容）
    file_name = Column(String(255), nullable=True)
    format = Column(String(16), nullable=True)  # Word / Excel
    total_questions = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    status = Column(String(16), default="completed")  # completed/failed/processing
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
