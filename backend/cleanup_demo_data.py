"""清理演示数据（幂等，可重复执行，物理删除不留演示数据）。

背景：项目自 2026-08 起彻底移除演示数据，启动时不再 seed 演示业务数据。
本脚本用于清理历史遗留的演示数据（本地 dev.db 与生产 PostgreSQL 通用），
执行后再次运行不会重复删除（按固定 code/file_name 精确匹配，二次执行均为 0）。

删除范围（全部为旧 seed_demo_data 曾创建的演示数据）：
- papers：paper_code IN ('P1','P2')，及其下游 paper_questions / answer_sheet_templates
- exam_tasks：全部（当前业务中所有考试任务均为演示任务），及其下游
  answer_sheets / question_scores / task_assignments / task_statistics
- classes：seed 固定 class_code A01/A02/B01/B02/C01
  （若仍有非演示学生引用该班级则跳过并告警，避免误删真实学生归属）
- teachers：seed 固定 teacher_code T001..T005，及 teacher_classes；
  受影响 users.teacher_id 置 NULL（admin/wang 等用户账号保留不删）
- students：seed 固定 student_code A01..A05/B01，及其 student_statistics
- import_logs：file_name IN ('初一数学试题库.docx','有理数专项练习.xlsx')
- categories：演示业务分类 qc1..qc5(question) / pc1..pc4(paper) / tc1..tc3(task)，
  同时把 questions / papers 中指向这些分类的引用置 NULL

保留范围（一律不动）：
- questions 全部真实题目
- users 全部账号（admin / wang 等）
- categories 基础分类（subject/grade/question_type/difficulty）
- tags、真实班级/教师/学生/试卷/任务/导入日志等其他真实数据

用法：
  本地： cd backend && venv/Scripts/python.exe cleanup_demo_data.py
  生产： cd /opt/ai-learning/backend && python cleanup_demo_data.py
"""
import sys

from app.core.db import SessionLocal
from app import models

# seed 造演示数据的固定编码清单（与旧 seed.py 完全一致，二次执行天然幂等）
DEMO_PAPER_CODES = ["P1", "P2"]
DEMO_CLASS_CODES = ["A01", "A02", "B01", "B02", "C01"]
DEMO_TEACHER_CODES = ["T001", "T002", "T003", "T004", "T005"]
DEMO_STUDENT_CODES = ["A01", "A02", "A03", "A04", "A05", "B01"]
DEMO_IMPORT_FILES = ["初一数学试题库.docx", "有理数专项练习.xlsx"]
# 演示业务分类：category_type -> code 列表
DEMO_CAT_SETS = {
    "question": ["qc1", "qc2", "qc3", "qc4", "qc5"],
    "paper": ["pc1", "pc2", "pc3", "pc4"],
    "task": ["tc1", "tc2", "tc3"],
}


def _delete(db, q, label):
    """执行批量删除并返回删除行数（幂等：空集返回 0）。"""
    count = q.delete(synchronize_session=False)
    if count:
        print(f"  - {label}: 删除 {count} 行")
    return count


def main():
    db = SessionLocal()
    try:
        print("开始清理演示数据...")

        # ---- 1. 考试任务及其下游（先删子表，再删父表，SQLite/PG 外键安全）----
        task_ids = [t[0] for t in db.query(models.ExamTask.id).all()]
        if task_ids:
            print(f"  考试任务（全部，共 {len(task_ids)} 个）：{task_ids}")
        _delete(db, db.query(models.QuestionScore), "question_scores")
        _delete(db, db.query(models.AnswerSheet), "answer_sheets")
        _delete(db, db.query(models.TaskAssignment), "task_assignments")
        _delete(db, db.query(models.TaskStatistic), "task_statistics")
        _delete(db, db.query(models.ExamTask), "exam_tasks")

        # ---- 2. 演示试卷 P1/P2 及其下游 ----
        paper_ids = [p[0] for p in db.query(models.Paper.id).filter(
            models.Paper.paper_code.in_(DEMO_PAPER_CODES)
        )]
        if paper_ids:
            _delete(
                db,
                db.query(models.AnswerSheetTemplate).filter(
                    models.AnswerSheetTemplate.paper_id.in_(paper_ids)
                ),
                f"answer_sheet_templates（试卷 {DEMO_PAPER_CODES}）",
            )
            _delete(
                db,
                db.query(models.PaperQuestion).filter(
                    models.PaperQuestion.paper_id.in_(paper_ids)
                ),
                f"paper_questions（试卷 {DEMO_PAPER_CODES}）",
            )
        _delete(
            db,
            db.query(models.Paper).filter(models.Paper.paper_code.in_(DEMO_PAPER_CODES)),
            f"papers {DEMO_PAPER_CODES}",
        )

        # ---- 3. 演示学生及其统计 ----
        stu_ids = [s[0] for s in db.query(models.Student.id).filter(
            models.Student.student_code.in_(DEMO_STUDENT_CODES)
        )]
        if stu_ids:
            _delete(
                db,
                db.query(models.StudentStatistic).filter(
                    models.StudentStatistic.student_id.in_(stu_ids)
                ),
                f"student_statistics（学生 {DEMO_STUDENT_CODES}）",
            )
        _delete(
            db,
            db.query(models.Student).filter(
                models.Student.student_code.in_(DEMO_STUDENT_CODES)
            ),
            f"students {DEMO_STUDENT_CODES}",
        )

        # ---- 4. 演示教师：先解除用户关联（保留账号），再删教师及班级关联 ----
        teacher_ids = [t[0] for t in db.query(models.Teacher.id).filter(
            models.Teacher.teacher_code.in_(DEMO_TEACHER_CODES)
        )]
        if teacher_ids:
            # 受影响用户的 teacher_id 置 NULL（admin/wang 等账号保留）
            affected = (
                db.query(models.User)
                .filter(models.User.teacher_id.in_(teacher_ids))
                .update({models.User.teacher_id: None}, synchronize_session=False)
            )
            if affected:
                print(f"  - users.teacher_id 置 NULL：{affected} 个用户（账号保留）")
            _delete(
                db,
                db.query(models.TeacherClass).filter(
                    models.TeacherClass.teacher_id.in_(teacher_ids)
                ),
                f"teacher_classes（教师 {DEMO_TEACHER_CODES}）",
            )
        _delete(
            db,
            db.query(models.Teacher).filter(
                models.Teacher.teacher_code.in_(DEMO_TEACHER_CODES)
            ),
            f"teachers {DEMO_TEACHER_CODES}",
        )

        # ---- 5. 演示班级：仅当无剩余学生引用时删除，避免破坏真实学生 ----
        class_ids = [c[0] for c in db.query(models.Class.id).filter(
            models.Class.class_code.in_(DEMO_CLASS_CODES)
        )]
        if class_ids:
            _delete(
                db,
                db.query(models.ClassStatistic).filter(
                    models.ClassStatistic.class_id.in_(class_ids)
                ),
                f"class_statistics（班级 {DEMO_CLASS_CODES}）",
            )
            # 剩余学生（非演示学生）仍引用的班级不能删，否则外键/归属被破坏
            safe_class_ids = list(class_ids)
            remaining = (
                db.query(models.Student)
                .filter(models.Student.class_id.in_(class_ids))
                .count()
            )
            if remaining:
                ref_codes = [
                    c.class_code
                    for c in db.query(models.Class).filter(models.Class.id.in_(class_ids)).all()
                    if db.query(models.Student).filter(models.Student.class_id == c.id).count()
                ]
                print(
                    f"  !! 班级 {ref_codes} 仍有 {remaining} 名学生引用，跳过删除（请人工确认）"
                )
                safe_class_ids = [
                    c.id
                    for c in db.query(models.Class).filter(models.Class.id.in_(class_ids)).all()
                    if not db.query(models.Student).filter(models.Student.class_id == c.id).count()
                ]
            _delete(
                db,
                db.query(models.Class).filter(models.Class.id.in_(safe_class_ids)),
                f"classes {DEMO_CLASS_CODES}",
            )

        # ---- 6. 演示导入日志 ----
        _delete(
            db,
            db.query(models.ImportLog).filter(
                models.ImportLog.file_name.in_(DEMO_IMPORT_FILES)
            ),
            f"import_logs {DEMO_IMPORT_FILES}",
        )

        # ---- 7. 演示业务分类：先解除真实数据引用，再删分类 ----
        # 按 (category_type, code) 成对精确匹配，避免误删同 code 的其他分类
        cat_pairs = [
            (ctype, code)
            for ctype, codes in DEMO_CAT_SETS.items()
            for code in codes
        ]
        cat_ids = []
        for ctype, code in cat_pairs:
            row = (
                db.query(models.Category.id)
                .filter(
                    models.Category.category_type == ctype,
                    models.Category.code == code,
                )
                .first()
            )
            if row:
                cat_ids.append(row[0])
        if cat_ids:
            # 真实题目/试卷若引用演示分类，置 NULL（分类删除后不产生悬空引用）
            ref_q = (
                db.query(models.Question)
                .filter(models.Question.category_id.in_(cat_ids))
                .update({models.Question.category_id: None}, synchronize_session=False)
            )
            if ref_q:
                print(f"  - questions.category_id 置 NULL：{ref_q} 题（题目保留）")
            ref_p = (
                db.query(models.Paper)
                .filter(models.Paper.category_id.in_(cat_ids))
                .update({models.Paper.category_id: None}, synchronize_session=False)
            )
            if ref_p:
                print(f"  - papers.category_id 置 NULL：{ref_p} 卷（试卷保留）")
        _delete(
            db,
            db.query(models.Category).filter(models.Category.id.in_(cat_ids)),
            f"categories 演示业务分类 {DEMO_CAT_SETS}",
        )

        db.commit()

        print("\n清理完成，当前遗留校验：")
        left_papers = db.query(models.Paper).filter(
            models.Paper.paper_code.in_(DEMO_PAPER_CODES)
        ).count()
        left_tasks = db.query(models.ExamTask).count()
        left_classes = db.query(models.Class).filter(
            models.Class.class_code.in_(DEMO_CLASS_CODES)
        ).count()
        left_students = db.query(models.Student).filter(
            models.Student.student_code.in_(DEMO_STUDENT_CODES)
        ).count()
        left_teachers = db.query(models.Teacher).filter(
            models.Teacher.teacher_code.in_(DEMO_TEACHER_CODES)
        ).count()
        left_imports = db.query(models.ImportLog).filter(
            models.ImportLog.file_name.in_(DEMO_IMPORT_FILES)
        ).count()
        left_cats = db.query(models.Category).filter(
            models.Category.id.in_(cat_ids)
        ).count() if cat_ids else 0
        print(f"  - 演示试卷残留: {left_papers}（应为 0）")
        print(f"  - 考试任务残留: {left_tasks}（应为 0）")
        print(f"  - 演示班级残留: {left_classes}（应为 0，除非有真实学生引用被跳过）")
        print(f"  - 演示学生残留: {left_students}（应为 0）")
        print(f"  - 演示教师残留: {left_teachers}（应为 0）")
        print(f"  - 演示导入日志残留: {left_imports}（应为 0）")
        print(f"  - 演示分类残留: {left_cats}（应为 0）")
        if any([left_papers, left_tasks, left_students, left_teachers, left_imports, left_cats]):
            sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
