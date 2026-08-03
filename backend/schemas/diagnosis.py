"""QuestionResult (diagnosis) schemas."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DiagnosisUpdate(BaseModel):
    teacher_verdict: Optional[str] = None
    teacher_note: Optional[str] = None
    is_typical: Optional[bool] = None
    verdict: Optional[str] = None
    kp_name: Optional[str] = None
    error_cause: Optional[str] = None
    skill_cause: Optional[str] = None
    ability_dimension: Optional[str] = None
    ai_explain: Optional[str] = None
    wrong_step: Optional[str] = None
    ocr_text: Optional[str] = None


class BatchConfirmRequest(BaseModel):
    diagnosis_ids: Optional[List[int]] = None
    min_confidence: float = 0.6


class DiagnosisOut(BaseModel):
    id: int
    task_id: int
    student_id: int
    question_number: int
    verdict: str
    ocr_text: str
    wrong_step: str
    primary_kp_id: Optional[int] = None
    related_kps: list = []
    kp_name: str
    error_cause: str
    skill_cause: str
    ability_dimension: str
    ai_explain: str
    ai_confidence: float
    ai_raw_json: str = "{}"
    is_typical: bool
    teacher_verdict: str
    teacher_note: str
    teacher_modified: bool
    confirmed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    # Joined fields
    task_name: str = ""
    student_name: str = ""

    class Config:
        from_attributes = True
