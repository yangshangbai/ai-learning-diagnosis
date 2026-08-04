"""Models package - imports all models for easy access and ensures they are registered."""

from database import Base

from models.user import User
from models.class_ import Grade, Class
from models.teacher import TeacherClass
from models.student import Student, StudentSnapshot
from models.task import Task, TaskClass
from models.knowledge import KnowledgePoint
from models.question import Question, QuestionSource, SourceOperation
from models.diagnosis import QuestionResult
from models.exercise import ExercisePlan
from models.audit import AuditLog

from models.ai_config import AIConfig
from models.error_log import ErrorLog
from models.feedback import Feedback

__all__ = [
    "Base",
    "User",
    "Grade",
    "Class",
    "TeacherClass",
    "Student",
    "StudentSnapshot",
    "Task",
    "TaskClass",
    "KnowledgePoint",
    "Question",
    "QuestionSource",
    "SourceOperation",
    "QuestionResult",
    "ExercisePlan",
    "AuditLog",
    "AIConfig",
    "ErrorLog",
    "Feedback",
]
