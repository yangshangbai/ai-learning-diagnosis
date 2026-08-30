"""种子数据：dev/test 自动建管理员账号与基础枚举。

项目自 2026-08 起彻底移除演示数据（Demo 业务数据 seed 已删除），
启动时不再自动创建班级/教师/学生/试卷/任务等演示数据。

生产不应自动建 admin；首次部署由运维用 CLI / 迁移脚本注入。
基础枚举（学科/年级/题型/难度）仅初始化一次，之后由用户在系统内维护。

所有 seed 函数均幂等：按 code/username 等业务键判断存在则跳过或更新。
"""
import datetime
import hashlib

from sqlalchemy import inspect, text

from .core.db import SessionLocal
from .core.logging import logger
from . import models


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _ensure_user_permissions_column(db):
    """权限模型升级：旧库 users 表补 permissions JSON 列（幂等，SQLite/PG 均适用）。"""
    try:
        insp = inspect(db.bind)
        if not insp.has_table("users"):
            return
        existing = {c["name"] for c in insp.get_columns("users")}
        if "permissions" not in existing:
            db.execute(text("ALTER TABLE users ADD COLUMN permissions JSON"))
            db.commit()
    except Exception:
        db.rollback()


def _ensure_paper_question_columns(db):
    """快照题型列（BUG-L015）：paper_questions 补 ques_type 并从题目回填存量（幂等，PG/SQLite 均适用）。"""
    try:
        insp = inspect(db.bind)
        if not insp.has_table("paper_questions"):
            return
        existing = {c["name"] for c in insp.get_columns("paper_questions")}
        if "ques_type" in existing:
            return
        db.execute(text("ALTER TABLE paper_questions ADD COLUMN ques_type VARCHAR(32)"))
        db.execute(text(
            "UPDATE paper_questions pq SET ques_type = q.ques_type "
            "FROM questions q WHERE pq.question_id = q.id"
        ))
        db.commit()
    except Exception:
        db.rollback()


def _migrate_default_permissions(db):
    """权限模型升级：给所有「非管理员且 permissions 为 NULL」的用户写入默认模块权限（幂等）。

    兼容存量 teacher 用户（如 wang）：自动获得除 用户管理/系统设置 外的所有模块 view+add+edit。
    """
    from .core.security import default_teacher_permissions

    users = (
        db.query(models.User)
        .filter(models.User.role != "admin", models.User.permissions.is_(None))
        .all()
    )
    if not users:
        return
    for u in users:
        u.permissions = default_teacher_permissions()
    db.commit()


def _ensure_question_columns(db):
    """防御：旧库 questions 表缺少 tags 列（批量设置标签用）。SQLite/PG 均适用，幂等。"""
    try:
        insp = inspect(db.bind)
        if not insp.has_table("questions"):
            return
        existing = {c["name"] for c in insp.get_columns("questions")}
        if "tags" not in existing:
            db.execute(text("ALTER TABLE questions ADD COLUMN tags JSON"))
            db.commit()
    except Exception:
        db.rollback()


def _seed_default_tags(db):
    """幂等：注入默认标签（首次初始化用），name 存在则跳过。"""
    defaults = [
        ("易错题", "red"),
        ("高频考点", "blue"),
        ("真题", "orange"),
        ("压轴题", "green"),
        ("计算训练", "blue"),
    ]
    added = 0
    for name, color in defaults:
        if db.query(models.Tag).filter(models.Tag.name == name).first():
            continue
        db.add(models.Tag(name=name, color=color))
        added += 1
    if added:
        db.commit()


# 位置编码学科前缀（与 seed_basic_data 的学科 code 一致）：
# 由 generate_question_code 按学科分类 code 生成，是可靠的学科信号
_SUBJECT_PREFIX_CODES = {"MAT", "CHN", "ENG", "PHY", "CHM"}


def _repair_question_subjects(db):
    """幂等修复题目学科错位（问题4 根因：学科字段错位 / 教研云 id 误当系统 category id）。

    判据：question_code 首位前缀（MAT/CHN/ENG/PHY/CHM）是可靠学科信号。对比当前 subject_id：
      - 当前值有效且与编码前缀一致 → 不动
      - 当前值缺失/NULL/越界/指向非 subject 分类，或与编码前缀不符 → 纠正为编码前缀对应学科 id
      - 编码前缀无法推断学科（code 缺失/未知前缀）→ 只记录不修改（无可靠判据）

    幂等：第二次运行时已修正题的 subject_id 与编码一致，fixed 为空。
    只修错的，不删除/重建数据。
    """
    subject_id_by_code = {}
    for c in db.query(models.Category).filter(models.Category.category_type == "subject").all():
        if c.code:
            subject_id_by_code[c.code] = c.id

    def subject_id_from_code(code):
        if not code:
            return None
        prefix = str(code).split("-")[0].strip().upper()
        return subject_id_by_code.get(prefix) if prefix in _SUBJECT_PREFIX_CODES else None

    def current_subject_ok(sid):
        if sid is None:
            return False
        c = db.query(models.Category).filter(models.Category.id == sid).first()
        return c is not None and c.category_type == "subject"

    fixed, skipped = [], []
    for q in db.query(models.Question).all():
        expected = subject_id_from_code(q.question_code)
        cur = q.subject_id
        if expected is not None and (not current_subject_ok(cur) or cur != expected):
            q.subject_id = expected
            fixed.append((q.id, cur, expected))
        elif expected is None and not current_subject_ok(cur):
            skipped.append((q.id, cur))

    if fixed or skipped:
        db.commit()
        if fixed:
            logger.warning(
                "question_subject_repair",
                extra={"fixed": len(fixed), "samples": fixed[:10]},
            )
        if skipped:
            logger.warning(
                "question_subject_repair_skipped",
                extra={"count": len(skipped), "samples": skipped[:10]},
            )
    return len(fixed), len(skipped)


def ensure_schema_migrations():
    """所有环境（含生产）启动时调用：幂等补列 / 建新表 / 默认标签 / 默认权限迁移 / 数据修复。

    - create_all：只创建缺失的表（如 tags），不会改动已有表与数据
    - ALTER TABLE：给旧 questions 表补 tags 列、旧 users 表补 permissions 列
    - _seed_default_tags：无则插入默认标签
    - _migrate_default_permissions：存量非管理员用户补默认模块权限
    - _repair_question_subjects：幂等纠正题目学科错位（问题4）
    """
    from .core.db import Base, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _ensure_question_columns(db)
        _ensure_user_permissions_column(db)
        _ensure_paper_question_columns(db)
        _migrate_default_permissions(db)
        _seed_default_tags(db)
        _repair_question_subjects(db)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 管理员账号
# ---------------------------------------------------------------------------
def seed_admin():
    db = SessionLocal()
    try:
        if db.query(models.User).filter(models.User.username == "admin").first():
            return
        db.add(
            models.User(
                username="admin",
                password_hash=_hash("admin123"),
                name="系统管理员",
                role="admin",
                is_active=True,
                created_at=_now(),
            )
        )
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 基础枚举（学科/年级/题型/难度——系统运行必需的基础分类，非演示数据）
# ---------------------------------------------------------------------------
def _upsert_category(db, category_type, code, name, sort_order=0, extra=None, status="active"):
    """按 (category_type, code) upsert；返回 category 行。"""
    row = (
        db.query(models.Category)
        .filter(
            models.Category.category_type == category_type,
            models.Category.code == code,
        )
        .first()
    )
    if row:
        row.name = name
        row.sort_order = sort_order
        row.extra = extra
        row.status = status
        return row
    row = models.Category(
        category_type=category_type,
        code=code,
        name=name,
        sort_order=sort_order,
        extra=extra,
        status=status,
    )
    db.add(row)
    db.flush()
    return row


def seed_basic_data():
    db = SessionLocal()
    try:
        # 学科（数学/语文/英语/物理/化学）
        for i, (code, name) in enumerate(
            [("MAT", "数学"), ("CHN", "语文"), ("ENG", "英语"), ("PHY", "物理"), ("CHM", "化学")]
        ):
            _upsert_category(db, "subject", code, name, sort_order=i)

        # 年级（12 个，含 stage；覆盖小初高全学段）
        grade_specs = [
            ("G1", "一年级", "primary"),
            ("G2", "二年级", "primary"),
            ("G3", "三年级", "primary"),
            ("G4", "四年级", "primary"),
            ("G5", "五年级", "primary"),
            ("G6", "六年级", "primary"),
            ("G7", "初一", "middle"),
            ("G8", "初二", "middle"),
            ("G9", "初三", "middle"),
            ("G10", "高一", "high"),
            ("G11", "高二", "high"),
            ("G12", "高三", "high"),
        ]
        for i, (code, name, stage) in enumerate(grade_specs):
            _upsert_category(db, "grade", code, name, sort_order=i, extra={"stage": stage})

        # 归档基础年级之外的旧年级（保证 meta 仅返回标准 12 个）
        demo_grade_codes = {c for c, _, _ in grade_specs}
        db.query(models.Category).filter(
            models.Category.category_type == "grade",
            ~models.Category.code.in_(demo_grade_codes),
        ).update({models.Category.status: "archived"}, synchronize_session=False)

        # 题型（5 种，含 short）
        qtype_specs = [
            ("single_choice", "单选题", "单选"),
            ("multi_choice", "多选题", "多选"),
            ("fill_blank", "填空题", "填空"),
            ("true_false", "判断题", "判断"),
            ("essay", "解答题", "解答"),
        ]
        for i, (code, name, short) in enumerate(qtype_specs):
            _upsert_category(db, "question_type", code, name, sort_order=i, extra={"short": short})

        # 难度（5 级，code=1..5）
        diff_specs = [
            ("1", "容易"),
            ("2", "较易"),
            ("3", "中等"),
            ("4", "较难"),
            ("5", "困难"),
        ]
        for i, (code, name) in enumerate(diff_specs):
            _upsert_category(db, "difficulty", code, name, sort_order=i + 1)

        db.commit()
    finally:
        db.close()
