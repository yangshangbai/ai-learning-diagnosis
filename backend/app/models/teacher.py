"""教师模型。

Teacher 关联 users 表（登录账号）。新建教师时一并创建 User(role=teacher)。
TeacherClass 表达教师-班级关联：每班仅 1 名班主任(head_teacher)，任课教师(subject_teacher)不限。
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Text, Boolean

from ..core.db import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    teacher_code = Column(String(32), nullable=True, unique=True, index=True)
    name = Column(String(64), nullable=False)
    gender = Column(String(8), nullable=True)  # male / female
    phone = Column(String(32), nullable=True)
    subject_ids = Column(JSON, nullable=True)  # 任教学科 category_id 数组
    remark = Column(Text, nullable=True)
    status = Column(String(16), default="active")  # active / archived
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TeacherClass(Base):
    __tablename__ = "teacher_classes"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # head_teacher / subject_teacher
    subject_id = Column(Integer, nullable=True, index=True)  # 任课教师任教学科
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
