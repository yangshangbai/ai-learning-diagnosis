"""导入日志 schemas：对齐 Demo 字段。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ImportLogOut(BaseModel):
    id: int
    file_name: Optional[str] = None
    format: Optional[str] = None
    total_questions: int = 0
    success_count: int = 0
    fail_count: int = 0
    status: str = "completed"
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedImportLog(BaseModel):
    items: list[ImportLogOut]
    total: int
    page: int
    page_size: int
