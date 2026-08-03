"""User model - teachers, admins, research admins, super admins."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(20), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    role = Column(String(20), nullable=False)  # teacher / admin / research / super
    password_hash = Column(String(256), nullable=False)
    avatar = Column(String(10), default="")
    grades = Column(Text, default="[]")  # JSON array
    subjects = Column(Text, default="[]")  # JSON array
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', role='{self.role}')>"
