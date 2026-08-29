"""基础数据模型：统一分类表 Category。

设计文档 §10.1：
- 枚举（仅改显示名）：subject(学科)/grade(年级)/question_type(题型)/difficulty(难度)
- 用户自定义树形：knowledge(知识点树)/question_bank(题库分类)/paper(试卷分类)/task(任务分类)
全部存放在同一张 categories 表，通过 category_type 区分。
知识点树用 parent_id 自引用；KP 编码写入 code 字段（如 KP003），全局唯一。
删除保护：有子节点或已被业务数据引用的分类不可删。
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, ForeignKey, Text

from ..core.db import Base


# category_type 取值
CAT_SUBJECT = "subject"
CAT_GRADE = "grade"
CAT_KNOWLEDGE = "knowledge"
CAT_QUESTION_TYPE = "question_type"
CAT_DIFFICULTY = "difficulty"
CAT_QUESTION_BANK = "question_bank"
CAT_QUESTION = "question"  # Demo 题库分类（与 question_bank 同义，Demo 用 "question"）
CAT_PAPER = "paper"
CAT_TASK = "task"

CATEGORY_TYPES = [
    CAT_SUBJECT,
    CAT_GRADE,
    CAT_KNOWLEDGE,
    CAT_QUESTION_TYPE,
    CAT_DIFFICULTY,
    CAT_QUESTION_BANK,
    CAT_QUESTION,
    CAT_PAPER,
    CAT_TASK,
]


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    category_type = Column(String(32), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    code = Column(String(64), nullable=True, index=True)  # 知识点 KP 码段 / 位置编码段
    sort_order = Column(Integer, default=0)
    extra = Column(JSON, nullable=True)
    status = Column(String(16), default="active")  # active / archived
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
