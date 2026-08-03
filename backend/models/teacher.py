"""Teacher-Class junction model."""

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class TeacherClass(Base):
    __tablename__ = "teacher_classes"

    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("users.id"))
    class_id = Column(Integer, ForeignKey("classes.id"))

    teacher = relationship("User")
    class_ = relationship("Class", back_populates="teacher_links")

    def __repr__(self):
        return f"<TeacherClass(teacher_id={self.teacher_id}, class_id={self.class_id})>"
