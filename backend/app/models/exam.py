"""考试任务与 AI 评分模型。

ExamTask：task_code 系统生成（T+YYYYMMDD+3 位流水）；status 六态。
TaskAssignment：任务-学生关联（class_id 创建时快照，学生转班不变）。
TaskStatistic：任务全景统计。
AnswerSheet：学生上传的答题卡（图片 URL 数组 + AI 状态）。
QuestionScore：每题评分（AI 评分 + 教师调分，final_score 教师优先）。
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Text, Float

from ..core.db import Base


class ExamTask(Base):
    __tablename__ = "exam_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_code = Column(String(32), nullable=True, unique=True, index=True)
    name = Column(String(255), nullable=False)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    creator_id = Column(Integer, ForeignKey("teachers.id"), nullable=True, index=True)
    status = Column(String(16), default="draft")  # draft/pending/in_exam/scoring/completed/voided
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("exam_tasks.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True, index=True)  # 创建时快照
    status = Column(String(16), default="pending")  # pending/uploaded/scored/confirmed


class TaskStatistic(Base):
    __tablename__ = "task_statistics"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("exam_tasks.id"), nullable=False, unique=True, index=True)
    question_count = Column(Integer, default=0)
    difficulty_avg = Column(Float, nullable=True)
    student_count = Column(Integer, default=0)
    upload_count = Column(Integer, default=0)
    upload_rate = Column(Float, nullable=True)
    avg_score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    min_score = Column(Float, nullable=True)
    median_score = Column(Float, nullable=True)
    std_deviation = Column(Float, nullable=True)
    pass_rate = Column(Float, nullable=True)
    excellent_rate = Column(Float, nullable=True)
    teacher_scored_count = Column(Integer, default=0)
    teacher_confirmed_count = Column(Integer, default=0)
    score_distribution = Column(JSON, nullable=True)
    question_correct_rate = Column(JSON, nullable=True)
    knowledge_performance = Column(JSON, nullable=True)
    type_performance = Column(JSON, nullable=True)
    difficulty_performance = Column(JSON, nullable=True)
    ai_teacher_deviation = Column(JSON, nullable=True)
    low_confidence_count = Column(Integer, default=0)
    low_confidence_questions = Column(JSON, nullable=True)
    class_comparison = Column(JSON, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AnswerSheet(Base):
    __tablename__ = "answer_sheets"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("exam_tasks.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    image_urls = Column(JSON, nullable=True)
    upload_type = Column(String(16), nullable=True)  # camera / file
    upload_device = Column(String(16), nullable=True)  # mobile / pc
    record_status = Column(String(16), default="active")  # active / superseded
    ai_status = Column(String(16), default="pending")  # pending/processing/completed/failed
    ai_started_at = Column(DateTime(timezone=True), nullable=True)
    ai_completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class QuestionScore(Base):
    __tablename__ = "question_scores"

    id = Column(Integer, primary_key=True, index=True)
    answer_sheet_id = Column(Integer, ForeignKey("answer_sheets.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("exam_tasks.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    paper_question_id = Column(Integer, ForeignKey("paper_questions.id"), nullable=False, index=True)
    question_number = Column(Integer, nullable=True)
    student_answer = Column(Text, nullable=True)
    correct_answer = Column(Text, nullable=True)
    ai_score = Column(Float, nullable=True)
    ai_max_score = Column(Integer, default=0)
    ai_confidence = Column(Float, nullable=True)  # 0-1
    ai_explanation = Column(Text, nullable=True)
    ai_raw_output = Column(JSON, nullable=True)
    teacher_score = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)
    score_status = Column(String(32), default="ai_scored")  # ai_scored/teacher_confirmed/teacher_modified
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
