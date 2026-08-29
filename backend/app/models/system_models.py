"""ORM 模型。

注意：
- users / system_logs 为本系统新建表；生产通过 Alembic 增量迁移创建，不覆盖 Demo 原表。
- system_logs 与系统设置下的「操作日志 audit_logs」职责不同：
    audit_logs = 业务操作审计（谁在何时改了什么）
    system_logs = 前后端错误归集（含 repaired 修复标记）
  二者并存，互不替代。
"""
import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)

from ..core.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    name = Column(String(50), nullable=True)
    role = Column(String(20), nullable=False, default="teacher")  # admin / teacher
    # 模块权限 JSON：{module: [action,...]}；admin 可为 NULL（视为全量放行）
    permissions = Column(JSON, nullable=True)
    teacher_id = Column(Integer, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=True)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(10), nullable=False, default="ERROR")  # ERROR/WARNING/INFO/DEBUG
    source = Column(String(10), nullable=False, default="backend")  # frontend/backend
    module = Column(String(50), nullable=True)
    message = Column(Text, nullable=False)
    detail = Column(Text, nullable=True)
    traceback = Column(Text, nullable=True)
    url = Column(String(500), nullable=True)
    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(50), nullable=True)
    request_id = Column(String(50), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
        index=True,
    )
    # 修复标记（需求点）
    repaired = Column(Boolean, default=False, nullable=False, index=True)
    repaired_at = Column(DateTime(timezone=True), nullable=True)
    repaired_by = Column(Integer, nullable=True)
    repaired_note = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_syslog_level_source", "level", "source"),
        Index("ix_syslog_repaired_created", "repaired", "created_at"),
    )
