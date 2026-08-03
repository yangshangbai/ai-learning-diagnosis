"""KnowledgePoint model - hierarchical knowledge tree."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, ForeignKey
from sqlalchemy.orm import relationship, backref
from database import Base


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=True)
    name = Column(String(200), nullable=False)
    subject = Column(String(20), default="")
    grade = Column(String(20), default="")
    stage = Column(String(20), default="")  # 小学 / 初中
    level = Column(Integer, default=1)  # 0=root, 1=subject, 2=module, 3=unit, 4=topic
    keywords = Column(Text, default="[]")  # JSON array
    sort_order = Column(Integer, default=0)
    mastery = Column(Float, default=0.0)  # 班级平均掌握度
    created_at = Column(DateTime, default=datetime.utcnow)

    children = relationship(
        "KnowledgePoint",
        backref=backref("parent", remote_side=[id]),
    )

    def __repr__(self):
        return f"<KnowledgePoint(id={self.id}, name='{self.name}', level={self.level})>"
