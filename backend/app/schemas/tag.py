"""标签 schemas。"""
from typing import Optional
from pydantic import BaseModel, field_validator
from datetime import datetime


class TagBase(BaseModel):
    name: str
    color: str = "blue"

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if not v or not v.strip():
            raise ValueError("name 不能为空")
        return v.strip()

    @field_validator("color")
    @classmethod
    def _color(cls, v):
        if v not in ("red", "blue", "orange", "green"):
            raise ValueError("color 必须是 red/blue/orange/green")
        return v


class TagCreate(TagBase):
    pass


class TagUpdate(TagBase):
    pass


class TagOut(TagBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
