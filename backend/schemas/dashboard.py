"""Dashboard statistics schemas."""

from pydantic import BaseModel
from typing import List


class DashboardStats(BaseModel):
    total_students: int = 0
    total_teachers: int = 0
    total_tasks: int = 0
    pending_review: int = 0
    ai_success_rate: float = 0.0
    avg_mastery: float = 0.0
    completion_rate: float = 0.0
    grade_distribution: list = []  # [{grade, count, mastery}]
    top_weaknesses: list = []  # [{kp_name, correct_rate, student_count}]
