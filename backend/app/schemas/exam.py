"""考试任务与 AI 评分 schemas。"""
from typing import Optional, List
from pydantic import Field, BaseModel, field_validator
from datetime import datetime


class ExamTaskCreate(BaseModel):
    name: str = Field(..., max_length=255)

    paper_id: int
    category_id: Optional[int] = None
    student_ids: Optional[List[int]] = None  # 创建时可直接分配学生

    @field_validator("name")
    @classmethod
    def _n(cls, v):
        if not v or not v.strip():
            raise ValueError("name 不能为空")
        return v.strip()


_EXAM_TASK_STATUS = {"draft", "pending", "in_exam", "scoring", "completed", "voided"}


class ExamTaskUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _status_enum(cls, v):
        if v is not None and v not in _EXAM_TASK_STATUS:
            raise ValueError(f"status 必须是 {sorted(_EXAM_TASK_STATUS)} 之一")
        return v


class ExamTaskOut(BaseModel):
    id: int
    task_code: Optional[str] = None
    name: str
    paper_id: int
    paper_name: Optional[str] = None
    category_id: Optional[int] = None
    category: Optional[str] = None
    creator_id: Optional[int] = None
    creator_name: Optional[str] = None
    status: str = "draft"
    student_count: int = 0
    class_ids: List[int] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedExamTask(BaseModel):
    items: List[ExamTaskOut]
    total: int
    page: int
    page_size: int


class TaskAssignmentOut(BaseModel):
    id: int
    task_id: int
    student_id: int
    class_id: Optional[int] = None
    status: str = "pending"
    student_name: Optional[str] = None
    student_code: Optional[str] = None

    model_config = {"from_attributes": True}


class RecognizedAnswerIn(BaseModel):
    question_number: int
    answer: str = ""


class AnswerSheetCreate(BaseModel):
    student_id: int
    image_urls: List[str] = []
    upload_type: Optional[str] = "file"  # camera / file
    upload_device: Optional[str] = "pc"  # mobile / pc
    answers: Optional[List[RecognizedAnswerIn]] = None  # 识别结果（题号→答案），随上传入库并由服务端判分


class AnswerSheetOut(BaseModel):
    id: int
    task_id: int
    student_id: int
    student_name: Optional[str] = None
    student_code: Optional[str] = None
    class_name: Optional[str] = None
    image_urls: Optional[List[str]] = None
    upload_type: Optional[str] = None
    upload_device: Optional[str] = None
    record_status: str = "active"
    ai_status: str = "pending"
    ai_total_score: Optional[float] = None
    teacher_total_score: Optional[float] = None
    final_score: Optional[float] = None
    question_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionScoreUpdate(BaseModel):
    teacher_score: Optional[float] = None
    teacher_comment: Optional[str] = None


class QuestionScoreOut(BaseModel):
    id: int
    answer_sheet_id: int
    task_id: int
    student_id: int
    paper_question_id: int
    question_number: Optional[int] = None
    student_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    ai_score: Optional[float] = None
    ai_max_score: int = 0
    ai_confidence: Optional[float] = None
    ai_explanation: Optional[str] = None
    teacher_score: Optional[float] = None
    final_score: Optional[float] = None
    score_status: str = "ai_scored"

    model_config = {"from_attributes": True}


class ExamDashboardOut(BaseModel):
    task_id: int
    question_count: int = 0
    student_count: int = 0
    upload_count: int = 0
    upload_rate: Optional[float] = None
    avg_score: Optional[float] = None
    max_score: Optional[float] = None
    min_score: Optional[float] = None
    pass_rate: Optional[float] = None
    excellent_rate: Optional[float] = None
    score_distribution: Optional[list] = None
    question_correct_rate: Optional[list] = None
    knowledge_performance: Optional[list] = None
    type_performance: Optional[list] = None
    difficulty_performance: Optional[list] = None
    low_confidence_count: int = 0

    model_config = {"from_attributes": True}
