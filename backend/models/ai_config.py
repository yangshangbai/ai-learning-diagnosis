"""AI configuration model for managing model selection and API keys."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from database import Base


class AIConfig(Base):
    __tablename__ = "ai_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), unique=True, nullable=False)  # openai, claude, paddle, zhipu, qwen, mock
    model_name = Column(String(100), default="")
    api_key = Column(Text, default="")          # displayed in plain text per requirement
    base_url = Column(String(500), default="")
    description = Column(String(200), default="")
    is_active = Column(Boolean, default=False)
    settings_json = Column(Text, default="{}")  # extra settings as JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AIConfig(provider='{self.provider}', active={self.is_active})>"
