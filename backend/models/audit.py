"""AuditLog model - operation audit trail."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator_name = Column(String(50))
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100))
    target = Column(String(200))
    ip_address = Column(String(50), default="")
    is_ai_call = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, operator='{self.operator_name}', action='{self.action}')>"
