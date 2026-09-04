"""问题需求（Case）模型：教师/管理员提交问题与改进需求，跟踪处理状态。"""
import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from ..core.db import Base


def _utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class Issue(Base):
    __tablename__ = "issues"

    # 状态机：pending 待处理 → processing 处理中 → done 已完成（completed_at 落完成时间）
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Case 编号：C + YYYYMMDD + 3位流水（当日内递增），唯一
    case_no = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    # 问题模块：题库管理/试卷管理/考试任务/学生管理/班级管理/教师管理/AI评分/AI选题/系统设置/其他
    module = Column(String(50), nullable=False, default="其他")
    description = Column(Text, nullable=False, default="")   # ≤500 字，后端校验
    images = Column(JSON, nullable=True)                     # ["/uploads/issues/xxx.png", ...]
    status = Column(String(20), nullable=False, default=STATUS_PENDING, index=True)
    created_by = Column(Integer, nullable=True, index=True)      # users.id
    created_by_name = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
