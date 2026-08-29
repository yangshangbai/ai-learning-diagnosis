# -*- coding: utf-8 -*-
"""任务2：备份并清除试卷/考试任务测试数据（含关联子表）。

执行前必须已确认备份成功。删除顺序按外键依赖：子表 → 父表。
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from app.core.db import SessionLocal
from app import models

BACKUP_DIR = "/opt/ai-learning/backup_20260814"
os.makedirs(BACKUP_DIR, exist_ok=True)

TABLES = [
    "question_scores", "answer_sheets", "task_assignments", "task_statistics",
    "exam_tasks", "paper_questions", "papers", "paper_drafts",
]

def dump_table(db, model, name):
    rows = db.query(model).all()
    data = [dict((c.name, getattr(r, c.name)) for c in model.__table__.columns) for r in rows]
    # datetime → str 可序列化
    def _ser(o):
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return o
    data = [{k: _ser(v) for k, v in row.items()} for row in data]
    path = os.path.join(BACKUP_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return len(data), path

def main():
    db = SessionLocal()
    try:
        print("== 备份阶段 ==")
        summary = {}
        for name in TABLES:
            model = getattr(models, {
                "question_scores": "QuestionScore",
                "answer_sheets": "AnswerSheet",
                "task_assignments": "TaskAssignment",
                "task_statistics": "TaskStatistic",
                "exam_tasks": "ExamTask",
                "paper_questions": "PaperQuestion",
                "papers": "Paper",
                "paper_drafts": "PaperDraft",
            }[name], None)
            if model is None:
                print("skip (no model):", name)
                continue
            n, p = dump_table(db, model, name)
            summary[name] = n
            print(f"  backed up {name}: {n} -> {p}")

        print("== 删除阶段（顺序：子表→父表）==")
        # 1. 评分/答题卡（依赖任务）
        n = db.query(models.QuestionScore).delete()
        print("  deleted question_scores:", n)
        n = db.query(models.AnswerSheet).delete()
        print("  deleted answer_sheets:", n)
        # 2. 任务关联/统计/任务
        n = db.query(models.TaskAssignment).delete()
        print("  deleted task_assignments:", n)
        n = db.query(models.TaskStatistic).delete()
        print("  deleted task_statistics:", n)
        n = db.query(models.ExamTask).delete()
        print("  deleted exam_tasks:", n)
        # 3. 试卷关联/试卷
        n = db.query(models.PaperQuestion).delete()
        print("  deleted paper_questions:", n)
        n = db.query(models.Paper).delete()
        print("  deleted papers:", n)
        # 4. 组卷草稿
        n = db.query(models.PaperDraft).delete()
        print("  deleted paper_drafts:", n)
        db.commit()
        print("== 清理完成 ==")
        print("backup summary:", json.dumps(summary, ensure_ascii=False))
    except Exception as e:
        db.rollback()
        print("ERROR, rolled back:", e)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
