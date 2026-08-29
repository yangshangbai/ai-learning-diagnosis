"""题库 schemas。"""
from typing import Optional, List
from pydantic import BaseModel, field_validator
from datetime import datetime

QUES_TYPES = ["single_choice", "multi_choice", "fill_blank", "true_false", "essay"]


class QuestionCreate(BaseModel):
    stem: str
    ques_type: str
    subject_id: Optional[int] = None
    grade_id: Optional[int] = None
    difficulty: int = 1
    options: Optional[list] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    score: int = 0
    knowledge_ids: Optional[List[int]] = None
    category_id: Optional[int] = None
    images: Optional[List[str]] = None
    source: str = "manual"
    source_id: Optional[str] = None
    tags: Optional[List[str]] = None

    @field_validator("stem")
    @classmethod
    def _stem(cls, v):
        if not v or not v.strip():
            raise ValueError("stem 不能为空")
        return v

    @field_validator("ques_type")
    @classmethod
    def _qt(cls, v):
        if v not in QUES_TYPES:
            raise ValueError(f"ques_type 必须是 {QUES_TYPES}")
        return v

    @field_validator("difficulty")
    @classmethod
    def _diff(cls, v):
        if not 1 <= v <= 5:
            raise ValueError("difficulty 必须是 1-5")
        return v


class QuestionUpdate(BaseModel):
    stem: Optional[str] = None
    ques_type: Optional[str] = None
    subject_id: Optional[int] = None
    grade_id: Optional[int] = None
    difficulty: Optional[int] = None
    options: Optional[list] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    score: Optional[int] = None
    knowledge_ids: Optional[List[int]] = None
    category_id: Optional[int] = None
    images: Optional[List[str]] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None


class QuestionOut(BaseModel):
    id: int
    question_code: Optional[str] = None
    source: str = "manual"
    source_id: Optional[str] = None
    subject_id: Optional[int] = None
    subject_name: Optional[str] = None
    grade_id: Optional[int] = None
    grade_name: Optional[str] = None
    ques_type: str
    difficulty: int = 1
    stem: str
    options: Optional[list] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    score: int = 0
    knowledge_ids: Optional[List[int]] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    tags: Optional[List[str]] = None
    images: Optional[List[str]] = None
    status: str = "active"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedQuestion(BaseModel):
    items: List[QuestionOut]
    total: int
    page: int
    page_size: int


class QuestionImportItem(BaseModel):
    stem: str
    ques_type: str
    subject_id: Optional[int] = None
    grade_id: Optional[int] = None
    # 按名称解析学科/年级（docx/OCR 导入从文件内容识别）：优先于 id；名称不存在时后端自动建分类
    subject_name: Optional[str] = None
    grade_name: Optional[str] = None
    difficulty: int = 1
    options: Optional[list] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    score: int = 0
    knowledge_ids: Optional[List[int]] = None
    category_id: Optional[int] = None
    source_id: Optional[str] = None
    tags: Optional[List[str]] = None

    @field_validator("answer", "analysis", mode="before")
    @classmethod
    def _join_list_text(cls, v):
        # 教研云答案/解析可能为数组：归一化为字符串，避免 422
        if isinstance(v, list):
            return " ".join(str(x) for x in v if x is not None)
        return v

    @field_validator("difficulty", "score", mode="before")
    @classmethod
    def _num(cls, v, info):
        # 教研云 difficulty/score 可能为 None 或字符串：转 int，None 用默认值
        if v is None:
            return 3 if info.field_name == "difficulty" else 0
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return v

    @field_validator("stem")
    @classmethod
    def _stem(cls, v):
        if not v or not v.strip():
            raise ValueError("stem 不能为空")
        return v

    @field_validator("ques_type")
    @classmethod
    def _qt(cls, v):
        if v not in QUES_TYPES:
            raise ValueError(f"ques_type 必须是 {QUES_TYPES}")
        return v


class QuestionImportRequest(BaseModel):
    items: List[QuestionImportItem]
