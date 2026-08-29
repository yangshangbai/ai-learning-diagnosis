"""试卷模板 & 答题卡模板 schemas。

PaperTemplateOut：单份模板文件元信息（对应 paper_templates / answer_sheet_templates 行）。
TemplateMetaOut：GET /template/meta 返回两份模板的元信息（前端显示"系统默认|已自定义"徽标用）。
"""
from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class PaperTemplateOut(BaseModel):
    """模板文件元信息：source=auto（系统默认）| user（用户上传覆盖）。"""
    source: str = "auto"
    file_name: Optional[str] = None
    file_type: str = "docx"
    file_size: int = 0
    file_path: Optional[str] = None
    updated_at: Optional[datetime] = None
    # 补充字段：文件是否实际存在（文件丢失时 source 会回落为 auto）
    exists: bool = False

    model_config = {"from_attributes": True}


class TemplateMetaOut(BaseModel):
    paper_template: PaperTemplateOut
    sheet_template: PaperTemplateOut
