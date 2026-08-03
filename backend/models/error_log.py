"""Error log model for tracking all API and frontend errors with repair status."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from database import Base


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    endpoint = Column(String(200), default="")
    method = Column(String(10), default="GET")
    error_type = Column(String(100), default="")          # e.g., "HTTPException", "TypeError", "AxiosError"
    error_message = Column(Text, default="")
    status_code = Column(Integer, default=500)
    stack_trace = Column(Text, default="")
    request_body = Column(Text, default="")
    user_id = Column(Integer, nullable=True)
    user_name = Column(String(50), default="")
    source = Column(String(20), default="backend")        # "backend" or "frontend"
    repair = Column(Boolean, default=False, index=True)   # ← Agent marks True after fixing
    repair_note = Column(Text, default="")
    repaired_at = Column(DateTime, nullable=True)
    repaired_by = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ErrorLog(id={self.id}, type='{self.error_type}', repair={self.repair})>"
