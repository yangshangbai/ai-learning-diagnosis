"""试卷模型。

Paper：paper_code 系统生成（P+YYYYMMDD+3 位流水）。
PaperQuestion：组卷快照（从题库复制 score/answer/analysis，试卷独立不随题库变更）。
AnswerSheetTemplate：答题卡布局（layout_config JSON，按题型宽度，见 §5.4）。
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Text

from ..core.db import Base


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    paper_code = Column(String(32), nullable=True, unique=True, index=True)
    name = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    subject_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    grade_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    total_score = Column(Integer, default=0)
    question_count = Column(Integer, default=0)
    remark = Column(Text, nullable=True)
    status = Column(String(16), default="draft")  # draft / active / archived
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PaperQuestion(Base):
    __tablename__ = "paper_questions"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True, index=True)
    sort_order = Column(Integer, default=0)
    score = Column(Integer, default=0)
    answer_key = Column(Text, nullable=True)
    analysis = Column(Text, nullable=True)


class AnswerSheetTemplate(Base):
    """答题卡模板：layout_config 为识别/排版结构配置（§5.4 按题型宽度）。
    文件模板字段（file_name/file_path/...）由增量迁移补列，与 PaperTemplate 同构。
    """

    __tablename__ = "answer_sheet_templates"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, unique=True, index=True)
    layout_config = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # ---- 以下列由 backend/migrate_templates.py 增量 ALTER 补列（不重建表）----
    file_name = Column(String(255), nullable=True)  # 上传/生成的原始文件名
    file_type = Column(String(20), default="docx")  # docx
    file_size = Column(Integer, default=0)
    file_path = Column(String(500), nullable=True)  # uploads/templates/sheet_<paperId>_<ts>.docx
    source = Column(String(20), default="auto")  # auto=系统生成 | user=用户上传覆盖
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PaperTemplate(Base):
    """试卷模板：用户可下载/修改/上传覆盖的 Word 母版 + layout_config 结构配置。

    - source='auto'：系统按默认规则生成；source='user'：用户上传覆盖。
    - 任务级渲染不建独立模板，直接继承本表的文件模板并运行时替换 QR。
    """

    __tablename__ = "paper_templates"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    file_name = Column(String(255), nullable=True)  # 上传/生成的原始文件名
    file_type = Column(String(20), default="docx")  # docx
    file_size = Column(Integer, default=0)
    file_path = Column(String(500), nullable=True)  # uploads/templates/paper_<paperId>_<ts>.docx
    layout_config = Column(JSON, nullable=True)  # 结构配置（与 AnswerSheetTemplate.layout_config 同构）
    source = Column(String(20), default="auto")  # auto=系统生成 | user=用户上传覆盖
    updated_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PaperDraft(Base):
    """组卷草稿（按用户隔离）：保存已选题目 id 列表，防止多用户互相干扰。"""

    __tablename__ = "paper_drafts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    questions = Column(JSON, nullable=True)  # 已选题目 id 列表（Demo 用 string id）
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AiSelectionBank(Base):
    """AI 选题库：AI 根据提示词自动拆解查询任务、检索教研云、分析选题拼装的结果。
    落表后等待用户确认，确认后同步到系统题库（questions）。"""

    __tablename__ = "ai_selection_banks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=True)          # 用户一行提示词
    subject_name = Column(String(64), nullable=True)
    grade_group_name = Column(String(32), nullable=True)
    grade_name = Column(String(32), nullable=True)
    semester = Column(String(32), nullable=True)
    category = Column(String(64), nullable=True)
    type_config = Column(JSON, nullable=True)           # {single_choice:3, fill_blank:2, essay:2}
    difficulty_ratio = Column(JSON, nullable=True)      # {easy:30, medium:50, hard:20}
    plan = Column(JSON, nullable=True)                  # AI 拆解出的查询计划
    questions = Column(JSON, nullable=True)             # 选中的题目列表（教研云题目对象）
    total_score = Column(Integer, default=0)
    status = Column(String(16), default="draft")        # draft / confirmed / synced
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
