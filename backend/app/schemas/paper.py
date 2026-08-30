"""试卷 schemas。"""
from typing import Optional, List
from pydantic import Field, BaseModel, field_validator
from datetime import datetime


class PaperCreate(BaseModel):
    name: str = Field(..., max_length=255)

    category_id: Optional[int] = None
    subject_id: Optional[int] = None
    grade_id: Optional[int] = None
    question_ids: List[int] = []
    remark: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _n(cls, v):
        if not v or not v.strip():
            raise ValueError("name 不能为空")
        return v.strip()


class PaperUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    subject_id: Optional[int] = None
    grade_id: Optional[int] = None
    remark: Optional[str] = None
    status: Optional[str] = None


class PaperQuestionOut(BaseModel):
    id: int
    paper_id: int
    question_id: Optional[int] = None  # 删题后置 NULL 保留快照（BUG-L010：非可选曾致 500）
    sort_order: int
    score: int
    answer_key: Optional[str] = None
    analysis: Optional[str] = None
    # 组卷快照返回时附带题干（来自 Question 表），便于前端"查看试卷题目"直接展示
    stem: str = ""

    model_config = {"from_attributes": True}


class PaperOut(BaseModel):
    id: int
    paper_code: Optional[str] = None
    name: str
    category_id: Optional[int] = None
    category: Optional[str] = None
    subject_id: Optional[int] = None
    subject: Optional[str] = None
    grade_id: Optional[int] = None
    grade: Optional[str] = None
    total_score: int = 0
    question_count: int = 0
    remark: Optional[str] = None
    status: str = "draft"
    created_at: datetime
    updated_at: datetime
    questions: List[int] = []  # 试卷题目 id 数组（前端 paperDetail 交叉引用）

    model_config = {"from_attributes": True}


class PaginatedPaper(BaseModel):
    items: List[PaperOut]
    total: int
    page: int
    page_size: int


class AnswerSheetTemplateOut(BaseModel):
    id: int
    paper_id: int
    layout_config: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}
