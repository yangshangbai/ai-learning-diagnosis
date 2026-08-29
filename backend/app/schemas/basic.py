"""基础数据 schemas：Category CRUD 与树形输出。"""
from typing import Optional, List
from pydantic import BaseModel, field_validator
from datetime import datetime

from ..models.basic import CATEGORY_TYPES


class CategoryCreate(BaseModel):
    name: str
    category_type: str
    parent_id: Optional[int] = None
    code: Optional[str] = None
    sort_order: int = 0
    extra: Optional[dict] = None

    @field_validator("category_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in CATEGORY_TYPES:
            raise ValueError(f"category_type 必须是 {CATEGORY_TYPES}")
        return v

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name 不能为空")
        return v.strip()


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    sort_order: Optional[int] = None
    extra: Optional[dict] = None
    status: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("name 不能为空")
        return v


class CategoryOut(BaseModel):
    id: int
    category_type: str
    parent_id: Optional[int] = None
    name: str
    code: Optional[str] = None
    sort_order: int = 0
    extra: Optional[dict] = None
    status: str = "active"
    # Demo 分类页需要 count（该分类下业务实体数；best-effort，无引用则为 0）
    count: Optional[int] = 0
    created_at: datetime
    updated_at: datetime
    children: List["CategoryOut"] = []

    model_config = {"from_attributes": True}


CategoryOut.model_rebuild()


class PaginatedCategory(BaseModel):
    items: List[CategoryOut]
    total: int
    page: int
    page_size: int
