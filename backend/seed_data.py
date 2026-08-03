"""
Seed data for the AI Learning Diagnosis System.

Populates all database tables with data matching the Demo prototype exactly.
Called once on first startup when the database is empty.
"""

import json
from datetime import date, datetime

import bcrypt
from sqlalchemy import text, select, func

from database import async_session_factory
from models.user import User
from models.class_ import Grade, Class
from models.teacher import TeacherClass
from models.student import Student, StudentSnapshot
from models.task import Task, TaskClass
from models.knowledge import KnowledgePoint
from models.question import Question, QuestionSource, SourceOperation
from models.diagnosis import QuestionResult
from models.exercise import ExercisePlan
from models.audit import AuditLog


PASSWORD_HASH = bcrypt.hashpw("demo123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# ===========================================================================
# Helper: check if DB is already seeded
# ===========================================================================
async def _is_seeded(session) -> bool:
    result = await session.execute(select(func.count()).select_from(User))
    count = result.scalar()
    return count > 0


# ===========================================================================
# Seed functions grouped by entity
# ===========================================================================
async def _seed_grades(session):
    grades = [
        Grade(id=1, name="五年级", sort_order=1),
        Grade(id=2, name="六年级", sort_order=2),
        Grade(id=3, name="初一", sort_order=3),
        Grade(id=4, name="初二", sort_order=4),
        Grade(id=5, name="初三", sort_order=5),
    ]
    session.add_all(grades)


async def _seed_classes(session):
    classes = [
        Class(id=1, name="五(1)班", grade_id=1, subjects=json.dumps(["数学"], ensure_ascii=False)),
        Class(id=2, name="五(2)班", grade_id=1, subjects=json.dumps(["数学"], ensure_ascii=False)),
        Class(id=3, name="六(1)班", grade_id=2, subjects=json.dumps(["数学"], ensure_ascii=False)),
        Class(id=4, name="六(2)班", grade_id=2, subjects=json.dumps(["数学"], ensure_ascii=False)),
        Class(id=5, name="初一(1)班", grade_id=3, subjects=json.dumps(["数学"], ensure_ascii=False)),
        Class(id=6, name="初一(2)班", grade_id=3, subjects=json.dumps(["数学"], ensure_ascii=False)),
        Class(id=7, name="初二(1)班", grade_id=4, subjects=json.dumps(["数学", "物理"], ensure_ascii=False)),
        Class(id=8, name="初二(2)班", grade_id=4, subjects=json.dumps(["数学", "物理"], ensure_ascii=False)),
        Class(id=9, name="初三(1)班", grade_id=5, subjects=json.dumps(["数学", "物理", "化学"], ensure_ascii=False)),
        Class(id=10, name="初三(2)班", grade_id=5, subjects=json.dumps(["数学", "物理", "化学"], ensure_ascii=False)),
    ]
    session.add_all(classes)


async def _seed_users(session):
    users = [
        # Teachers (t1-t5)
        User(id=1, phone="13800001111", name="李老师", role="teacher",
             password_hash=PASSWORD_HASH, avatar="李",
             grades=json.dumps(["五年级"], ensure_ascii=False),
             subjects=json.dumps(["数学"], ensure_ascii=False)),
        User(id=2, phone="13800002222", name="张老师", role="teacher",
             password_hash=PASSWORD_HASH, avatar="张",
             grades=json.dumps(["六年级"], ensure_ascii=False),
             subjects=json.dumps(["数学"], ensure_ascii=False)),
        User(id=3, phone="13800003333", name="王老师", role="teacher",
             password_hash=PASSWORD_HASH, avatar="王",
             grades=json.dumps(["初一"], ensure_ascii=False),
             subjects=json.dumps(["数学"], ensure_ascii=False)),
        User(id=4, phone="13800004444", name="赵老师", role="teacher",
             password_hash=PASSWORD_HASH, avatar="赵",
             grades=json.dumps(["初二"], ensure_ascii=False),
             subjects=json.dumps(["数学", "物理"], ensure_ascii=False)),
        User(id=5, phone="13800005555", name="钱老师", role="teacher",
             password_hash=PASSWORD_HASH, avatar="钱",
             grades=json.dumps(["初三"], ensure_ascii=False),
             subjects=json.dumps(["数学", "物理", "化学"], ensure_ascii=False)),
        # Admins (a1-a3)
        User(id=6, phone="13900001111", name="王校长", role="admin",
             password_hash=PASSWORD_HASH, avatar="王",
             grades=json.dumps([], ensure_ascii=False),
             subjects=json.dumps([], ensure_ascii=False)),
        User(id=7, phone="13900002222", name="赵教研", role="research",
             password_hash=PASSWORD_HASH, avatar="赵",
             grades=json.dumps([], ensure_ascii=False),
             subjects=json.dumps([], ensure_ascii=False)),
        User(id=8, phone="13900003333", name="超级管理员", role="super",
             password_hash=PASSWORD_HASH, avatar="超",
             grades=json.dumps([], ensure_ascii=False),
             subjects=json.dumps([], ensure_ascii=False)),
    ]
    session.add_all(users)


async def _seed_teacher_classes(session):
    links = [
        TeacherClass(id=1, teacher_id=1, class_id=1),
        TeacherClass(id=2, teacher_id=1, class_id=2),
        TeacherClass(id=3, teacher_id=2, class_id=3),
        TeacherClass(id=4, teacher_id=2, class_id=4),
        TeacherClass(id=5, teacher_id=3, class_id=5),
        TeacherClass(id=6, teacher_id=3, class_id=6),
        TeacherClass(id=7, teacher_id=4, class_id=7),
        TeacherClass(id=8, teacher_id=4, class_id=8),
        TeacherClass(id=9, teacher_id=5, class_id=9),
        TeacherClass(id=10, teacher_id=5, class_id=10),
    ]
    session.add_all(links)


async def _seed_students(session):
    students = [
        Student(id=1, name="张三", class_id=1, mastery=85, trend="up",
                weak_points=json.dumps(["分数通分"], ensure_ascii=False), avatar_color="#4F46E5"),
        Student(id=2, name="李四", class_id=1, mastery=72, trend="stable",
                weak_points=json.dumps(["三角形面积"], ensure_ascii=False), avatar_color="#7C3AED"),
        Student(id=3, name="王五", class_id=1, mastery=58, trend="down",
                weak_points=json.dumps(["异分母分数加减", "分数应用题"], ensure_ascii=False), avatar_color="#EF4444"),
        Student(id=4, name="赵六", class_id=2, mastery=91, trend="up",
                weak_points=json.dumps([], ensure_ascii=False), avatar_color="#10B981"),
        Student(id=5, name="钱七", class_id=2, mastery=67, trend="down",
                weak_points=json.dumps(["长方体体积"], ensure_ascii=False), avatar_color="#F59E0B"),
        Student(id=6, name="孙八", class_id=3, mastery=78, trend="up",
                weak_points=json.dumps(["百分数应用"], ensure_ascii=False), avatar_color="#6366F1"),
        Student(id=7, name="周九", class_id=3, mastery=63, trend="down",
                weak_points=json.dumps(["分数乘除", "比例"], ensure_ascii=False), avatar_color="#EC4899"),
        Student(id=8, name="吴十", class_id=4, mastery=82, trend="up",
                weak_points=json.dumps([], ensure_ascii=False), avatar_color="#14B8A6"),
        Student(id=9, name="郑一", class_id=5, mastery=75, trend="stable",
                weak_points=json.dumps(["一元一次方程"], ensure_ascii=False), avatar_color="#4F46E5"),
        Student(id=10, name="冯二", class_id=5, mastery=68, trend="down",
                weak_points=json.dumps(["有理数运算"], ensure_ascii=False), avatar_color="#7C3AED"),
        Student(id=11, name="陈三", class_id=6, mastery=88, trend="up",
                weak_points=json.dumps([], ensure_ascii=False), avatar_color="#10B981"),
        Student(id=12, name="褚四", class_id=7, mastery=71, trend="stable",
                weak_points=json.dumps(["一次函数", "浮力"], ensure_ascii=False), avatar_color="#F59E0B"),
        Student(id=13, name="卫五", class_id=7, mastery=55, trend="down",
                weak_points=json.dumps(["三角形全等", "压强"], ensure_ascii=False), avatar_color="#EF4444"),
        Student(id=14, name="蒋六", class_id=8, mastery=83, trend="up",
                weak_points=json.dumps(["电路分析"], ensure_ascii=False), avatar_color="#6366F1"),
        Student(id=15, name="沈七", class_id=9, mastery=76, trend="stable",
                weak_points=json.dumps(["二次函数", "化学方程式"], ensure_ascii=False), avatar_color="#EC4899"),
        Student(id=16, name="韩八", class_id=9, mastery=62, trend="down",
                weak_points=json.dumps(["圆的证明", "欧姆定律", "酸碱盐"], ensure_ascii=False), avatar_color="#EF4444"),
        Student(id=17, name="杨九", class_id=10, mastery=89, trend="up",
                weak_points=json.dumps([], ensure_ascii=False), avatar_color="#14B8A6"),
        Student(id=18, name="朱十", class_id=10, mastery=70, trend="stable",
                weak_points=json.dumps(["电功率", "化学计算"], ensure_ascii=False), avatar_color="#F59E0B"),
        Student(id=19, name="李十一", class_id=2, mastery=45, trend="down",
                weak_points=json.dumps(["分数加减", "通分"], ensure_ascii=False), avatar_color="#EF4444"),
        Student(id=20, name="王十二", class_id=3, mastery=82, trend="up",
                weak_points=json.dumps(["几何证明"], ensure_ascii=False), avatar_color="#10B981"),
        Student(id=21, name="赵十三", class_id=4, mastery=63, trend="stable",
                weak_points=json.dumps(["百分数概念", "比例"], ensure_ascii=False), avatar_color="#6366F1"),
        Student(id=22, name="钱十四", class_id=4, mastery=38, trend="down",
                weak_points=json.dumps(["分数乘除", "百分数应用", "简易方程"], ensure_ascii=False), avatar_color="#EC4899"),
        Student(id=23, name="孙十五", class_id=5, mastery=79, trend="up",
                weak_points=json.dumps(["一元一次方程"], ensure_ascii=False), avatar_color="#14B8A6"),
        Student(id=24, name="周十六", class_id=6, mastery=56, trend="down",
                weak_points=json.dumps(["有理数运算", "整式运算"], ensure_ascii=False), avatar_color="#EF4444"),
        Student(id=25, name="吴十七", class_id=6, mastery=84, trend="up",
                weak_points=json.dumps([], ensure_ascii=False), avatar_color="#10B981"),
        Student(id=26, name="郑十八", class_id=7, mastery=67, trend="stable",
                weak_points=json.dumps(["一次函数", "压强"], ensure_ascii=False), avatar_color="#F59E0B"),
        Student(id=27, name="冯十九", class_id=8, mastery=49, trend="down",
                weak_points=json.dumps(["串并联电路", "浮力"], ensure_ascii=False), avatar_color="#EF4444"),
        Student(id=28, name="陈二十", class_id=8, mastery=78, trend="up",
                weak_points=json.dumps(["欧姆定律"], ensure_ascii=False), avatar_color="#6366F1"),
        Student(id=29, name="褚二一", class_id=9, mastery=54, trend="down",
                weak_points=json.dumps(["二次函数", "化学方程式"], ensure_ascii=False), avatar_color="#EC4899"),
        Student(id=30, name="卫二二", class_id=10, mastery=93, trend="up",
                weak_points=json.dumps([], ensure_ascii=False), avatar_color="#14B8A6"),
    ]
    session.add_all(students)


async def _seed_tasks(session):
    tasks = [
        Task(id=1, name="第三单元周测-分数", type="周测", subject="数学", grade="五年级",
             difficulty="中等", pages=4, objective="检测分数加减法和分数基本概念的掌握情况",
             status="pending_review",
             kps=json.dumps(["分数概念", "同分母分数加减", "异分母分数加减", "分数比较"], ensure_ascii=False),
             confirmed_count=8, total_count=15, creator_id=1,
             class_ids=json.dumps([1, 2], ensure_ascii=False),
             created_at=datetime(2026, 7, 15)),
        Task(id=2, name="日常作业-三角形全等", type="日常作业", subject="数学", grade="五年级",
             difficulty="基础", pages=2, objective="巩固三角形全等判定定理的运用",
             status="ai_processing",
             kps=json.dumps(["三角形全等", "三角形面积"], ensure_ascii=False),
             confirmed_count=0, total_count=8, creator_id=1,
             class_ids=json.dumps([1], ensure_ascii=False),
             created_at=datetime(2026, 7, 16)),
        Task(id=3, name="专项练习-分数应用题", type="专项练习", subject="数学", grade="五年级",
             difficulty="拔高", pages=4, objective="强化分数在实际问题中的建模能力",
             status="pending_upload",
             kps=json.dumps(["分数应用题建模", "分数四则混合运算"], ensure_ascii=False),
             confirmed_count=0, total_count=0, creator_id=1,
             class_ids=json.dumps([2], ensure_ascii=False),
             created_at=datetime(2026, 7, 17)),
        Task(id=4, name="阶段测-电路分析", type="阶段测", subject="物理", grade="初二",
             difficulty="中等", pages=6, objective="检测欧姆定律和电路分析的综合运用",
             status="pending_review",
             kps=json.dumps(["欧姆定律", "串并联电路", "电功率"], ensure_ascii=False),
             confirmed_count=5, total_count=20, creator_id=4,
             class_ids=json.dumps([7, 8], ensure_ascii=False),
             created_at=datetime(2026, 7, 14)),
        Task(id=5, name="期末模拟-数学", type="期末模拟", subject="数学", grade="初三",
             difficulty="拔高", pages=8, objective="全真模拟中考数学",
             status="draft",
             kps=json.dumps(["二次函数", "圆的证明", "概率统计", "三角函数"], ensure_ascii=False),
             confirmed_count=0, total_count=0, creator_id=5,
             class_ids=json.dumps([9, 10], ensure_ascii=False),
             created_at=datetime(2026, 7, 17)),
        Task(id=6, name="周测-百分数与比例", type="周测", subject="数学", grade="六年级",
             difficulty="中等", pages=4, objective="检测百分数概念、百分数应用和比例的基本掌握情况",
             status="pending_review",
             kps=json.dumps(["百分数概念", "百分数应用", "比例", "分数比较"], ensure_ascii=False),
             confirmed_count=6, total_count=12, creator_id=2,
             class_ids=json.dumps([3, 4], ensure_ascii=False),
             created_at=datetime(2026, 7, 15)),
        Task(id=7, name="阶段测-方程与不等式", type="阶段测", subject="数学", grade="初一",
             difficulty="中等", pages=6, objective="检测一元一次方程、不等式组和二元一次方程组的综合运用",
             status="ai_processing",
             kps=json.dumps(["一元一次方程", "二元一次方程组", "不等式组", "整式运算"], ensure_ascii=False),
             confirmed_count=0, total_count=18, creator_id=3,
             class_ids=json.dumps([5, 6], ensure_ascii=False),
             created_at=datetime(2026, 7, 16)),
        Task(id=8, name="专项练习-力学综合", type="专项练习", subject="物理", grade="初二",
             difficulty="中等", pages=5, objective="强化压强、浮力和简单机械的解题能力",
             status="completed",
             kps=json.dumps(["压强", "浮力", "简单机械", "力学基础"], ensure_ascii=False),
             confirmed_count=15, total_count=15, creator_id=4,
             class_ids=json.dumps([7, 8], ensure_ascii=False),
             created_at=datetime(2026, 7, 13)),
        Task(id=9, name="期末模拟-化学", type="期末模拟", subject="化学", grade="初三",
             difficulty="拔高", pages=8, objective="全真模拟中考化学，覆盖酸碱盐和化学计算",
             status="draft",
             kps=json.dumps(["化学方程式", "酸碱盐", "化学计算", "四大反应类型"], ensure_ascii=False),
             confirmed_count=0, total_count=0, creator_id=5,
             class_ids=json.dumps([9, 10], ensure_ascii=False),
             created_at=datetime(2026, 7, 17)),
        Task(id=10, name="日常作业-分数通分练习", type="日常作业", subject="数学", grade="五年级",
             difficulty="基础", pages=2, objective="巩固同分母和异分母分数加减的通分技巧",
             status="pending_upload",
             kps=json.dumps(["同分母分数加减", "异分母分数加减", "分数概念"], ensure_ascii=False),
             confirmed_count=0, total_count=0, creator_id=1,
             class_ids=json.dumps([1, 2], ensure_ascii=False),
             created_at=datetime(2026, 7, 17)),
    ]
    session.add_all(tasks)


async def _seed_task_classes(session):
    links = [
        TaskClass(id=1, task_id=1, class_id=1),
        TaskClass(id=2, task_id=1, class_id=2),
        TaskClass(id=3, task_id=2, class_id=1),
        TaskClass(id=4, task_id=3, class_id=2),
        TaskClass(id=5, task_id=4, class_id=7),
        TaskClass(id=6, task_id=4, class_id=8),
        TaskClass(id=7, task_id=5, class_id=9),
        TaskClass(id=8, task_id=5, class_id=10),
        TaskClass(id=9, task_id=6, class_id=3),
        TaskClass(id=10, task_id=6, class_id=4),
        TaskClass(id=11, task_id=7, class_id=5),
        TaskClass(id=12, task_id=7, class_id=6),
        TaskClass(id=13, task_id=8, class_id=7),
        TaskClass(id=14, task_id=8, class_id=8),
        TaskClass(id=15, task_id=9, class_id=9),
        TaskClass(id=16, task_id=9, class_id=10),
        TaskClass(id=17, task_id=10, class_id=1),
        TaskClass(id=18, task_id=10, class_id=2),
    ]
    session.add_all(links)


# ===========================================================================
# Knowledge Tree - matching Demo knowledgeTree array exactly
# ===========================================================================
async def _seed_knowledge_tree(session):
    kps = [
        # ---- 小学数学 (root) ----
        KnowledgePoint(id=1, parent_id=None, name="小学数学", subject="数学", stage="小学", level=0, keywords="[]"),
        # 数与代数
        KnowledgePoint(id=2, parent_id=1, name="数与代数", subject="数学", stage="小学", level=1, keywords="[]"),
        # 分数
        KnowledgePoint(id=3, parent_id=2, name="分数", subject="数学", stage="小学", level=2, keywords="[]"),
        KnowledgePoint(id=4, parent_id=3, name="分数概念", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]", mastery=0.85),
        KnowledgePoint(id=5, parent_id=3, name="同分母分数加减", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]", mastery=0.90),
        KnowledgePoint(id=6, parent_id=3, name="异分母分数加减", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]", mastery=0.52),
        KnowledgePoint(id=7, parent_id=3, name="分数比较", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]", mastery=0.78),
        KnowledgePoint(id=8, parent_id=3, name="分数与小数互化", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]", mastery=0.70),
        KnowledgePoint(id=9, parent_id=3, name="分数乘除法", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]", mastery=0.82),
        # 百分数
        KnowledgePoint(id=10, parent_id=2, name="百分数", subject="数学", stage="小学", level=2, keywords="[]"),
        KnowledgePoint(id=11, parent_id=10, name="百分数概念", subject="数学", grade="六年级", stage="小学", level=3, keywords="[]"),
        KnowledgePoint(id=12, parent_id=10, name="百分数应用", subject="数学", grade="六年级", stage="小学", level=3, keywords="[]"),
        # 方程
        KnowledgePoint(id=13, parent_id=2, name="方程", subject="数学", stage="小学", level=2, keywords="[]"),
        KnowledgePoint(id=14, parent_id=13, name="简易方程", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]", mastery=0.75),
        KnowledgePoint(id=15, parent_id=13, name="方程建模", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]", mastery=0.60),
        # 图形与几何
        KnowledgePoint(id=16, parent_id=1, name="图形与几何", subject="数学", stage="小学", level=1, keywords="[]"),
        # 三角形
        KnowledgePoint(id=17, parent_id=16, name="三角形", subject="数学", stage="小学", level=2, keywords="[]"),
        KnowledgePoint(id=18, parent_id=17, name="三角形面积", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]", mastery=0.72),
        KnowledgePoint(id=19, parent_id=17, name="三角形全等", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]", mastery=0.85),
        # 长方体
        KnowledgePoint(id=20, parent_id=16, name="长方体", subject="数学", stage="小学", level=2, keywords="[]"),
        KnowledgePoint(id=21, parent_id=20, name="长方体体积", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]", mastery=0.65),
        KnowledgePoint(id=22, parent_id=20, name="长方体表面积", subject="数学", grade="五年级", stage="小学", level=3, keywords="[]"),

        # ---- 初中数学 (root) ----
        KnowledgePoint(id=30, parent_id=None, name="初中数学", subject="数学", stage="初中", level=0, keywords="[]"),
        # 数与式
        KnowledgePoint(id=31, parent_id=30, name="数与式", subject="数学", stage="初中", level=1, keywords="[]"),
        KnowledgePoint(id=32, parent_id=31, name="有理数运算", subject="数学", grade="初一", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=33, parent_id=31, name="实数", subject="数学", grade="初一", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=34, parent_id=31, name="整式运算", subject="数学", grade="初一", stage="初中", level=3, keywords="[]"),
        # 方程与不等式
        KnowledgePoint(id=35, parent_id=30, name="方程与不等式", subject="数学", stage="初中", level=1, keywords="[]"),
        KnowledgePoint(id=36, parent_id=35, name="一元一次方程", subject="数学", grade="初一", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=37, parent_id=35, name="二元一次方程组", subject="数学", grade="初一", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=38, parent_id=35, name="一元二次方程", subject="数学", grade="初三", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=39, parent_id=35, name="不等式组", subject="数学", grade="初一", stage="初中", level=3, keywords="[]"),
        # 函数
        KnowledgePoint(id=40, parent_id=30, name="函数", subject="数学", stage="初中", level=1, keywords="[]"),
        KnowledgePoint(id=41, parent_id=40, name="一次函数", subject="数学", grade="初二", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=42, parent_id=40, name="反比例函数", subject="数学", grade="初三", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=43, parent_id=40, name="二次函数", subject="数学", grade="初三", stage="初中", level=3, keywords="[]"),
        # 几何
        KnowledgePoint(id=44, parent_id=30, name="几何", subject="数学", stage="初中", level=1, keywords="[]"),
        KnowledgePoint(id=45, parent_id=44, name="三角形全等", subject="数学", grade="初二", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=46, parent_id=44, name="相似三角形", subject="数学", grade="初三", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=47, parent_id=44, name="勾股定理", subject="数学", grade="初二", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=48, parent_id=44, name="四边形", subject="数学", grade="初二", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=49, parent_id=44, name="圆的证明", subject="数学", grade="初三", stage="初中", level=3, keywords="[]"),
        # 统计与概率
        KnowledgePoint(id=50, parent_id=30, name="统计与概率", subject="数学", stage="初中", level=1, keywords="[]"),
        KnowledgePoint(id=51, parent_id=50, name="数据分析", subject="数学", grade="初三", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=52, parent_id=50, name="概率计算", subject="数学", grade="初三", stage="初中", level=3, keywords="[]"),

        # ---- 初中物理 (root) ----
        KnowledgePoint(id=60, parent_id=None, name="初中物理", subject="物理", stage="初中", level=0, keywords="[]"),
        # 力学
        KnowledgePoint(id=61, parent_id=60, name="力学", subject="物理", stage="初中", level=1, keywords="[]"),
        KnowledgePoint(id=62, parent_id=61, name="压强", subject="物理", grade="初二", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=63, parent_id=61, name="浮力", subject="物理", grade="初二", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=64, parent_id=61, name="简单机械", subject="物理", grade="初二", stage="初中", level=3, keywords="[]"),
        # 电学
        KnowledgePoint(id=65, parent_id=60, name="电学", subject="物理", stage="初中", level=1, keywords="[]"),
        KnowledgePoint(id=66, parent_id=65, name="欧姆定律", subject="物理", grade="初二", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=67, parent_id=65, name="串并联电路", subject="物理", grade="初二", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=68, parent_id=65, name="电功率", subject="物理", grade="初三", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=69, parent_id=65, name="电路分析", subject="物理", grade="初三", stage="初中", level=3, keywords="[]"),
        # 光学
        KnowledgePoint(id=70, parent_id=60, name="光学", subject="物理", stage="初中", level=1, keywords="[]"),
        KnowledgePoint(id=71, parent_id=70, name="反射定律", subject="物理", grade="初二", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=72, parent_id=70, name="凸透镜成像", subject="物理", grade="初二", stage="初中", level=3, keywords="[]"),

        # ---- 初中化学 (root) ----
        KnowledgePoint(id=80, parent_id=None, name="初中化学", subject="化学", stage="初中", level=0, keywords="[]"),
        # 物质构成
        KnowledgePoint(id=81, parent_id=80, name="物质构成", subject="化学", stage="初中", level=1, keywords="[]"),
        KnowledgePoint(id=82, parent_id=81, name="化学式与化合价", subject="化学", grade="初三", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=83, parent_id=81, name="化学方程式", subject="化学", grade="初三", stage="初中", level=3, keywords="[]"),
        # 化学反应
        KnowledgePoint(id=84, parent_id=80, name="化学反应", subject="化学", stage="初中", level=1, keywords="[]"),
        KnowledgePoint(id=85, parent_id=84, name="四大反应类型", subject="化学", grade="初三", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=86, parent_id=84, name="化学计算", subject="化学", grade="初三", stage="初中", level=3, keywords="[]"),
        # 酸碱盐
        KnowledgePoint(id=87, parent_id=80, name="酸碱盐", subject="化学", stage="初中", level=1, keywords="[]"),
        KnowledgePoint(id=88, parent_id=87, name="酸的性质", subject="化学", grade="初三", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=89, parent_id=87, name="碱的性质", subject="化学", grade="初三", stage="初中", level=3, keywords="[]"),
        KnowledgePoint(id=90, parent_id=87, name="盐的性质", subject="化学", grade="初三", stage="初中", level=3, keywords="[]"),
    ]
    session.add_all(kps)


# ===========================================================================
# Questions - matching Demo questions + external candidates
# ===========================================================================
async def _seed_questions(session):
    questions = [
        # Core questions (q1-q6 from Demo)
        Question(id=1, title="计算: 2/3 + 1/4 - 5/6 = ?", type="计算题",
                 subject="数学", grade="五年级", difficulty=2,
                 kp_name="异分母分数加减", kp_id=6, source="本地题库"),
        Question(id=2, title="一个长方体水箱长8dm宽5dm高6dm，求它的容积是多少升？", type="应用题",
                 subject="数学", grade="五年级", difficulty=2,
                 kp_name="长方体体积", kp_id=21, source="本地题库"),
        Question(id=3, title="解方程: 3(x-2) = 2x + 4", type="计算题",
                 subject="数学", grade="初一", difficulty=2,
                 kp_name="一元一次方程", kp_id=36, source="本地题库"),
        Question(id=4, title="已知二次函数y=2x\u00b2-4x+1，求其顶点坐标和最小值", type="解答题",
                 subject="数学", grade="初三", difficulty=3,
                 kp_name="二次函数", kp_id=43, source="教研云",
                 external_id="JYY-M-202607-1042", sync_status="已同步"),
        Question(id=5, title="一个电阻为10\u03a9的用电器接在220V电源上，求通过它的电流和功率", type="计算题",
                 subject="物理", grade="初二", difficulty=2,
                 kp_name="欧姆定律", kp_id=66, source="教研云",
                 external_id="JYY-P-202607-2088", sync_status="已同步"),
        Question(id=6, title="写出铁与稀盐酸反应的化学方程式", type="填空题",
                 subject="化学", grade="初三", difficulty=1,
                 kp_name="化学方程式", kp_id=83, source="本地题库"),
        # External candidates (5 from Demo externalCandidates)
        Question(id=7, title="比较5/6和7/9的大小，并说明理由", type="解答题",
                 subject="数学", grade="五年级", difficulty=1,
                 kp_name="分数比较", kp_id=7, source="教研云",
                 external_id="JYY-M-202607-3101", sync_status="已入库"),
        Question(id=8, title="计算7/12+5/18，并写出通分过程", type="计算题",
                 subject="数学", grade="五年级", difficulty=2,
                 kp_name="异分母分数加减", kp_id=6, source="教研云",
                 external_id="JYY-M-202607-3102", sync_status="已入库"),
        Question(id=9, title="一段路已修3/8，剩下125米，这段路全长多少米？", type="应用题",
                 subject="数学", grade="五年级", difficulty=2,
                 kp_name="分数应用题建模", kp_id=15, source="教研云",
                 external_id="JYY-M-202607-3103", sync_status="已入库"),
        Question(id=10, title="小明把2/5+1/3算成3/8，请分析错误并订正", type="纠错题",
                 subject="数学", grade="五年级", difficulty=2,
                 kp_name="异分母分数加减", kp_id=6, source="教研云",
                 external_id="JYY-M-202607-3104", sync_status="已入库"),
        Question(id=11, title="设计一道结果等于1的异分母分数加法题", type="开放题",
                 subject="数学", grade="五年级", difficulty=3,
                 kp_name="异分母分数加减", kp_id=6, source="教研云",
                 external_id="JYY-M-202607-3105", sync_status="已入库"),
    ]
    session.add_all(questions)


# ===========================================================================
# Question Source config
# ===========================================================================
async def _seed_question_sources(session):
    source = QuestionSource(
        id=1,
        name="教研云",
        status="running",
        priority="external_first",
        on_demand=True,
        scheduled_sync=True,
        fallback=True,
        schedule="每日 02:00",
        min_pool=30,
        last_sync="今天 16:20",
        mapping_coverage=96,
        quality_pass_rate=94,
    )
    session.add(source)


async def _seed_source_operations(session):
    ops = [
        SourceOperation(id=1, source_id=1, time="今天 16:20", type="增量搬运",
                        detail="教研云新增42题，入库35题，7题进入待处理", status="完成"),
        SourceOperation(id=2, source_id=1, time="今天 15:48", type="老师出题调用",
                        detail="李老师 \u00b7 王五 \u00b7 异分母分数加减 \u00b7 自动匹配10题", status="完成"),
        SourceOperation(id=3, source_id=1, time="今天 14:10", type="规则调整",
                        detail="赵教研将小学数学设为教研云优先，本地题库兜底", status="已生效"),
        SourceOperation(id=4, source_id=1, time="昨天 02:00", type="定时同步",
                        detail="完成全学科增量检查，更新18题", status="完成"),
    ]
    session.add_all(ops)


# ===========================================================================
# Diagnosis results - matching Demo diagnoses array (10 questions for tk1, s3)
# ===========================================================================
async def _seed_question_results(session):
    results = [
        QuestionResult(id=1, task_id=1, student_id=3, question_number=1,
                       verdict="correct", ocr_text="3/8 + 2/8 = 5/8", wrong_step="无",
                       primary_kp_id=4, related_kps=json.dumps(["同分母分数加减"], ensure_ascii=False),
                       kp_name="分数概念", error_cause="", skill_cause="无",
                       ability_dimension="概念理解能力",
                       ai_explain="学生正确理解了分数基本概念，过程和结果均正确",
                       ai_confidence=0.95, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=2, task_id=1, student_id=3, question_number=2,
                       verdict="correct", ocr_text="7/9 - 2/9 = 5/9", wrong_step="无",
                       primary_kp_id=5, related_kps=json.dumps(["分数概念"], ensure_ascii=False),
                       kp_name="同分母分数加减", error_cause="", skill_cause="无",
                       ability_dimension="运算能力",
                       ai_explain="同分母计算扎实，分母保持不变、分子相减正确",
                       ai_confidence=0.93, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=3, task_id=1, student_id=3, question_number=3,
                       verdict="incorrect", ocr_text="1/3 + 1/2 = 2/5",
                       wrong_step="未先通分，直接分子分母分别相加",
                       primary_kp_id=6, related_kps=json.dumps(["通分", "分数基本性质"], ensure_ascii=False),
                       kp_name="异分母分数加减", error_cause="概念混淆", skill_cause="程序性知识错误",
                       ability_dimension="概念理解能力",
                       ai_explain="未通分直接相加。正确做法应先通分为2/6+3/6=5/6",
                       ai_confidence=0.91, is_typical=True,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=4, task_id=1, student_id=3, question_number=4,
                       verdict="correct", ocr_text="3/5 > 4/9", wrong_step="无",
                       primary_kp_id=7, related_kps=json.dumps(["通分"], ensure_ascii=False),
                       kp_name="分数比较", error_cause="", skill_cause="无",
                       ability_dimension="逻辑推理能力",
                       ai_explain="分数大小比较方法正确，能选择通分后比较",
                       ai_confidence=0.94, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=5, task_id=1, student_id=3, question_number=5,
                       verdict="partially_correct", ocr_text="1/8 = 0.12",
                       wrong_step="小数换算末位漏写5",
                       primary_kp_id=8, related_kps=json.dumps(["除法计算"], ensure_ascii=False),
                       kp_name="分数与小数互化", error_cause="计算失误", skill_cause="S型-计算细节错误",
                       ability_dimension="运算能力",
                       ai_explain="思路正确，但1/8转化为小数时计算错误，应为0.125",
                       ai_confidence=0.87, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=6, task_id=1, student_id=3, question_number=6,
                       verdict="incorrect", ocr_text="剩下部分直接乘总量",
                       wrong_step="遗漏题干中\u201c剩下的\u201d这一条件",
                       primary_kp_id=15, related_kps=json.dumps(["单位1识别", "分数乘法"], ensure_ascii=False),
                       kp_name="分数应用题建模", error_cause="建模失败", skill_cause="审题偏差",
                       ability_dimension="应用建模能力",
                       ai_explain="未能将实际问题转化为分数模型，审题遗漏关键条件",
                       ai_confidence=0.88, is_typical=True,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=7, task_id=1, student_id=3, question_number=7,
                       verdict="correct", ocr_text="2/5 \u00d7 15 = 6", wrong_step="无",
                       primary_kp_id=9, related_kps=json.dumps(["整数乘法"], ensure_ascii=False),
                       kp_name="分数乘法", error_cause="", skill_cause="无",
                       ability_dimension="运算能力",
                       ai_explain="分数乘法运算正确，单位处理完整",
                       ai_confidence=0.96, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=8, task_id=1, student_id=3, question_number=8,
                       verdict="incorrect", ocr_text="先算加法再算乘法",
                       wrong_step="四则混合运算顺序错误",
                       primary_kp_id=9, related_kps=json.dumps(["分数乘除法", "运算顺序"], ensure_ascii=False),
                       kp_name="分数四则混合运算", error_cause="策略不当", skill_cause="程序性知识错误",
                       ability_dimension="逻辑推理能力",
                       ai_explain="运算顺序错误，未按先乘除后加减的规则",
                       ai_confidence=0.92, is_typical=True,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=9, task_id=1, student_id=3, question_number=9,
                       verdict="correct", ocr_text="x = 3/4", wrong_step="无",
                       primary_kp_id=14, related_kps=json.dumps(["等式性质"], ensure_ascii=False),
                       kp_name="分数方程", error_cause="", skill_cause="无",
                       ability_dimension="表达规范能力",
                       ai_explain="分数方程求解步骤完整正确，书写规范",
                       ai_confidence=0.90, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=10, task_id=1, student_id=3, question_number=10,
                       verdict="uncertain", ocr_text="字迹模糊，仅能识别部分步骤",
                       wrong_step="关键列式区域无法识别",
                       primary_kp_id=6, related_kps=json.dumps(["分数应用题建模", "审题能力"], ensure_ascii=False),
                       kp_name="综合应用题", error_cause="需人工判断", skill_cause="低置信度-需人工补录",
                       ability_dimension="审题能力",
                       ai_explain="学生作答部分正确但字迹模糊，部分步骤难以确认",
                       ai_confidence=0.55, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),
    ]
    session.add_all(results)


async def _seed_question_results_extra(session):
    """Additional diagnoses: 10 for task 6 (math, grade 6, student 7) + 10 for task 4 (physics, grade 8, student 12)."""
    results = [
        # ---- Task 6 (数学 六年级, 周测) - Student 7 (周九, class 3) ----
        QuestionResult(id=11, task_id=6, student_id=7, question_number=1,
                       verdict="correct", ocr_text="75% = 0.75 = 3/4", wrong_step="无",
                       primary_kp_id=11, related_kps=json.dumps(["分数与小数互化"], ensure_ascii=False),
                       kp_name="百分数概念", error_cause="", skill_cause="无",
                       ability_dimension="概念理解能力",
                       ai_explain="百分数与小数、分数的互化掌握扎实，转换正确",
                       ai_confidence=0.94, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=12, task_id=6, student_id=7, question_number=2,
                       verdict="incorrect", ocr_text="80\u00d70.2=16, \u2234\u6253\u6298\u540e\u4ef716\u5143",
                       wrong_step="将\u201c打八折\u201d理解为打二折",
                       primary_kp_id=12, related_kps=json.dumps(["百分数概念", "实际应用"], ensure_ascii=False),
                       kp_name="百分数应用", error_cause="概念混淆", skill_cause="审题偏差",
                       ability_dimension="应用建模能力",
                       ai_explain="将\u201c八折\u201d误解为减去80%，应理解为原价\u00d780%",
                       ai_confidence=0.90, is_typical=True,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=13, task_id=6, student_id=7, question_number=3,
                       verdict="correct", ocr_text="5/6 > 7/9\uff0c\u901a\u5206\u540e 15/18 > 14/18", wrong_step="无",
                       primary_kp_id=7, related_kps=json.dumps(["通分", "分数基本性质"], ensure_ascii=False),
                       kp_name="分数比较", error_cause="", skill_cause="无",
                       ability_dimension="逻辑推理能力",
                       ai_explain="分数大小比较方法正确，通分后比较分子，步骤完整",
                       ai_confidence=0.96, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=14, task_id=6, student_id=7, question_number=4,
                       verdict="partially_correct", ocr_text="3:5\u6233:10 = 6:10\u6233:10",
                       wrong_step="化简比时未除以最大公约数",
                       primary_kp_id=12, related_kps=json.dumps(["比例", "约分"], ensure_ascii=False),
                       kp_name="比例应用", error_cause="计算失误", skill_cause="S型-计算细节错误",
                       ability_dimension="运算能力",
                       ai_explain="比例化简思路正确但步骤有误，未找到最大公约数",
                       ai_confidence=0.85, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=15, task_id=6, student_id=7, question_number=5,
                       verdict="correct", ocr_text="40\u00d71.25 = 50", wrong_step="无",
                       primary_kp_id=12, related_kps=json.dumps(["百分数概念"], ensure_ascii=False),
                       kp_name="百分数应用", error_cause="", skill_cause="无",
                       ability_dimension="运算能力",
                       ai_explain="\u201c增加25%\u201d理解为\u00d71.25，计算正确",
                       ai_confidence=0.93, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=16, task_id=6, student_id=7, question_number=6,
                       verdict="incorrect", ocr_text="空白",
                       wrong_step="完全未作答",
                       primary_kp_id=12, related_kps=json.dumps(["分数乘除", "单位1识别"], ensure_ascii=False),
                       kp_name="百分数综合应用", error_cause="建模失败", skill_cause="程序性知识错误",
                       ability_dimension="应用建模能力",
                       ai_explain="学生面对复杂百分数应用题无从下手，未建立数学模型",
                       ai_confidence=0.88, is_typical=True,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=17, task_id=6, student_id=7, question_number=7,
                       verdict="correct", ocr_text="6:8:10 = 3:4:5", wrong_step="无",
                       primary_kp_id=7, related_kps=json.dumps(["比例"], ensure_ascii=False),
                       kp_name="比例化简", error_cause="", skill_cause="无",
                       ability_dimension="运算能力",
                       ai_explain="连比化简正确，步骤清晰，结果规范",
                       ai_confidence=0.95, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=18, task_id=6, student_id=7, question_number=8,
                       verdict="incorrect", ocr_text="\u76f4\u63a5\u7528\u5206\u5b50\u5206\u6bcd\u76f8\u4e58",
                       wrong_step="分数乘法与加法规则混淆",
                       primary_kp_id=9, related_kps=json.dumps(["分数加减", "分数乘除"], ensure_ascii=False),
                       kp_name="分数乘除法", error_cause="概念混淆", skill_cause="程序性知识错误",
                       ability_dimension="概念理解能力",
                       ai_explain="将分数乘法规则错误应用于分数加法，混淆两种运算",
                       ai_confidence=0.91, is_typical=True,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=19, task_id=6, student_id=7, question_number=9,
                       verdict="correct", ocr_text="解:\u8bbex\u4e2a\uff0c3x+2x=30\uff0cx=6", wrong_step="无",
                       primary_kp_id=14, related_kps=json.dumps(["方程建模"], ensure_ascii=False),
                       kp_name="简易方程", error_cause="", skill_cause="无",
                       ability_dimension="表达规范能力",
                       ai_explain="列方程解应用题步骤完整，设未知数合理，计算正确",
                       ai_confidence=0.92, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=20, task_id=6, student_id=7, question_number=10,
                       verdict="uncertain", ocr_text="字迹潦草，答案被涂改多次",
                       wrong_step="最终答案与过程不一致",
                       primary_kp_id=12, related_kps=json.dumps(["百分数概念", "审题能力"], ensure_ascii=False),
                       kp_name="百分数综合应用", error_cause="需人工判断", skill_cause="低置信度-需人工补录",
                       ability_dimension="审题能力",
                       ai_explain="作答过程与最终答案存在矛盾，有涂改痕迹，需人工确认",
                       ai_confidence=0.52, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        # ---- Task 4 (物理 初二, 阶段测) - Student 12 (褚四, class 7) ----
        QuestionResult(id=21, task_id=4, student_id=12, question_number=1,
                       verdict="correct", ocr_text="I = U/R = 6/12 = 0.5A", wrong_step="无",
                       primary_kp_id=66, related_kps=json.dumps(["电流计算"], ensure_ascii=False),
                       kp_name="欧姆定律", error_cause="", skill_cause="无",
                       ability_dimension="运算能力",
                       ai_explain="欧姆定律应用正确，公式选择恰当，单位换算无误",
                       ai_confidence=0.95, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=22, task_id=4, student_id=12, question_number=2,
                       verdict="incorrect", ocr_text="\u4e32\u8054\u7535\u8def\u603b\u7535\u963b R = R1+R2 = 10+10 = 30\u03a9",
                       wrong_step="串联电阻简单相加出错",
                       primary_kp_id=67, related_kps=json.dumps(["欧姆定律", "电阻"], ensure_ascii=False),
                       kp_name="串并联电路", error_cause="计算失误", skill_cause="S型-计算细节错误",
                       ability_dimension="运算能力",
                       ai_explain="串联电阻公式正确但计算错误，10+10误算为30",
                       ai_confidence=0.89, is_typical=True,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=23, task_id=4, student_id=12, question_number=3,
                       verdict="correct", ocr_text="P = U\u00b2/R = 220\u00b2/100 = 484W", wrong_step="无",
                       primary_kp_id=68, related_kps=json.dumps(["欧姆定律", "功率公式"], ensure_ascii=False),
                       kp_name="电功率", error_cause="", skill_cause="无",
                       ability_dimension="运算能力",
                       ai_explain="电功率计算公式选择正确，计算过程完整",
                       ai_confidence=0.94, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=24, task_id=4, student_id=12, question_number=4,
                       verdict="partially_correct", ocr_text="\u753b\u51fa\u4e86\u7535\u8def\u56fe\u4f46\u6f0f\u6807\u7535\u6d41\u65b9\u5411",
                       wrong_step="电路图中未标注电流方向",
                       primary_kp_id=69, related_kps=json.dumps(["串并联电路", "电流"], ensure_ascii=False),
                       kp_name="电路分析", error_cause="表达不规范", skill_cause="S型-规范性错误",
                       ability_dimension="表达规范能力",
                       ai_explain="电路结构分析正确，但缺少电流方向标注，表达不够完整",
                       ai_confidence=0.82, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=25, task_id=4, student_id=12, question_number=5,
                       verdict="correct", ocr_text="p = F/S = 500/0.5 = 1000Pa", wrong_step="无",
                       primary_kp_id=62, related_kps=json.dumps(["力学基础"], ensure_ascii=False),
                       kp_name="压强", error_cause="", skill_cause="无",
                       ability_dimension="应用建模能力",
                       ai_explain="压强公式应用正确，单位换算准确，计算无误",
                       ai_confidence=0.93, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=26, task_id=4, student_id=12, question_number=6,
                       verdict="incorrect", ocr_text="\u8ba4\u4e3a\u6d6e\u529b\u7b49\u4e8e\u7269\u4f53\u91cd\u529b",
                       wrong_step="混淆漂浮与悬浮条件",
                       primary_kp_id=63, related_kps=json.dumps(["力学基础", "阿基米德原理"], ensure_ascii=False),
                       kp_name="浮力", error_cause="概念混淆", skill_cause="程序性知识错误",
                       ability_dimension="概念理解能力",
                       ai_explain="未区分物体漂浮与悬浮的受力区别，浮力等于排开液体重力而非物体重力",
                       ai_confidence=0.87, is_typical=True,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=27, task_id=4, student_id=12, question_number=7,
                       verdict="correct", ocr_text="\u52a8\u6ed1\u8f6e\u7701\u4e00\u534a\u529b\u4f46\u8d39\u8ddd\u79bb", wrong_step="无",
                       primary_kp_id=64, related_kps=json.dumps(["力学基础", "功"], ensure_ascii=False),
                       kp_name="简单机械", error_cause="", skill_cause="无",
                       ability_dimension="概念理解能力",
                       ai_explain="动滑轮省力原理理解正确，能准确描述省力不省功的特点",
                       ai_confidence=0.91, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=28, task_id=4, student_id=12, question_number=8,
                       verdict="incorrect", ocr_text="\u5c06\u5e76\u8054\u7535\u8def\u503c\u5f53\u4f5c\u4e32\u8054\u8ba1\u7b97",
                       wrong_step="并联电路中误用串联公式计算总电阻",
                       primary_kp_id=67, related_kps=json.dumps(["欧姆定律", "电路分析"], ensure_ascii=False),
                       kp_name="串并联电路", error_cause="概念混淆", skill_cause="程序性知识错误",
                       ability_dimension="逻辑推理能力",
                       ai_explain="未能区分串并联电路的电阻计算规则，并联电路应使用倒数求和",
                       ai_confidence=0.90, is_typical=True,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=29, task_id=4, student_id=12, question_number=9,
                       verdict="correct", ocr_text="\u5149\u4ece\u7a7a\u6c14\u659c\u5c04\u5165\u6c34\u4e2d\uff0c\u6298\u5c04\u89d2\u5c0f\u4e8e\u5165\u5c04\u89d2", wrong_step="无",
                       primary_kp_id=71, related_kps=json.dumps(["折射定律"], ensure_ascii=False),
                       kp_name="反射定律", error_cause="", skill_cause="无",
                       ability_dimension="概念理解能力",
                       ai_explain="光的折射规律掌握正确，能准确描述光从疏介质到密介质的折射方向",
                       ai_confidence=0.92, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),

        QuestionResult(id=30, task_id=4, student_id=12, question_number=10,
                       verdict="uncertain", ocr_text="\u7b54\u6848\u90e8\u5206\u88ab\u64e6\u9664\uff0c\u6b8b\u7559\u75d5\u8ff9\u65e0\u6cd5\u5224\u8bfb",
                       wrong_step="关键计算步骤被涂抹",
                       primary_kp_id=69, related_kps=json.dumps(["电功率", "复杂电路"], ensure_ascii=False),
                       kp_name="复杂电路综合", error_cause="需人工判断", skill_cause="低置信度-需人工补录",
                       ability_dimension="审题能力",
                       ai_explain="复杂电路综合分析题，学生过程被涂抹，仅残留部分正确列式",
                       ai_confidence=0.48, is_typical=False,
                       ai_raw_json=json.dumps({}, ensure_ascii=False)),
    ]
    session.add_all(results)


# ===========================================================================
# Exercise plans - matching Demo plans
# ===========================================================================
async def _seed_exercise_plans(session):
    plans = [
        ExercisePlan(id=1, student_id=1, student_name="张三",
                     target_kp="分数通分+分数应用", frequency="每周3次",
                     question_count=15, difficulty="中等",
                     source="统一智能题库", source_trace="教研云12题 + 本地3题",
                     status="进行中", effect="改善中"),
        ExercisePlan(id=2, student_id=3, student_name="王五",
                     target_kp="异分母分数加减", frequency="每天1次",
                     question_count=10, difficulty="基础",
                     source="统一智能题库", source_trace="本地10题",
                     status="进行中", effect="待观察"),
        ExercisePlan(id=3, student_id=6, student_name="孙八",
                     target_kp="几何证明", frequency="每周3次",
                     question_count=12, difficulty="中等",
                     source="统一智能题库", source_trace="教研云8题 + 本地4题",
                     status="进行中", effect="改善中"),
        ExercisePlan(id=4, student_id=14, student_name="蒋六",
                     target_kp="电路分析", frequency="每天1次",
                     question_count=8, difficulty="基础",
                     source="统一智能题库", source_trace="本地8题",
                     status="进行中", effect="待观察"),
        ExercisePlan(id=5, student_id=15, student_name="沈七",
                     target_kp="化学方程式配平", frequency="每周1次",
                     question_count=15, difficulty="拔高",
                     source="统一智能题库", source_trace="教研云10题 + 本地5题",
                     status="已暂停", effect="待观察"),
    ]
    session.add_all(plans)


# ===========================================================================
# Audit logs - matching Demo logs (5 from index.html)
# ===========================================================================
async def _seed_audit_logs(session):
    logs = [
        AuditLog(id=1, operator_name="李老师", operator_id=1,
                 action="修改诊断结论", target="张三 - 题3",
                 ip_address="192.168.1.100", is_ai_call=False,
                 created_at=datetime(2026, 7, 17, 14, 30)),
        AuditLog(id=2, operator_name="王校长", operator_id=6,
                 action="远程协助-代上传", target="李老师 - 周测任务",
                 ip_address="192.168.1.200", is_ai_call=True,
                 created_at=datetime(2026, 7, 17, 11, 15)),
        AuditLog(id=3, operator_name="系统", operator_id=None,
                 action="AI批改完成", target="作业-三角形全等 (20份)",
                 ip_address="-", is_ai_call=True,
                 created_at=datetime(2026, 7, 17, 10, 0)),
        AuditLog(id=4, operator_name="赵教研", operator_id=7,
                 action="发布知识库更新", target="知识点体系 v2.3",
                 ip_address="192.168.1.150", is_ai_call=False,
                 created_at=datetime(2026, 7, 16, 16, 45)),
        AuditLog(id=5, operator_name="李老师", operator_id=1,
                 action="导出阶段报告", target="张三 - 7月诊断报告",
                 ip_address="192.168.1.100", is_ai_call=False,
                 created_at=datetime(2026, 7, 16, 9, 20)),
        AuditLog(id=6, operator_name="张老师", operator_id=2,
                 action="创建新任务", target="周测-百分数与比例",
                 ip_address="192.168.1.101", is_ai_call=False,
                 created_at=datetime(2026, 7, 15, 8, 30)),
        AuditLog(id=7, operator_name="王校长", operator_id=6,
                 action="修改组织架构", target="将初一(2)班调整为数学+英语双学科",
                 ip_address="192.168.1.200", is_ai_call=False,
                 created_at=datetime(2026, 7, 16, 14, 0)),
        AuditLog(id=8, operator_name="赵老师", operator_id=4,
                 action="批量确认诊断结论", target="阶段测-电路分析 (15份)",
                 ip_address="192.168.1.103", is_ai_call=False,
                 created_at=datetime(2026, 7, 14, 17, 45)),
        AuditLog(id=9, operator_name="系统", operator_id=None,
                 action="AI批改完成", target="阶段测-方程与不等式 (18份)",
                 ip_address="-", is_ai_call=True,
                 created_at=datetime(2026, 7, 16, 18, 30)),
        AuditLog(id=10, operator_name="系统", operator_id=None,
                 action="AI任务处理完成", target="日常作业-三角形全等 批改+诊断已生成",
                 ip_address="-", is_ai_call=True,
                 created_at=datetime(2026, 7, 16, 11, 0)),
        AuditLog(id=11, operator_name="超级管理员", operator_id=8,
                 action="修改系统配置", target="调整AI置信度阈值为0.6",
                 ip_address="192.168.1.50", is_ai_call=False,
                 created_at=datetime(2026, 7, 15, 10, 0)),
        AuditLog(id=12, operator_name="赵教研", operator_id=7,
                 action="审核外部题库题目", target="学科网-数学-7题通过审核入库",
                 ip_address="192.168.1.150", is_ai_call=False,
                 created_at=datetime(2026, 7, 17, 9, 15)),
    ]
    session.add_all(logs)


# ===========================================================================
# Student Snapshots - historical learning data
# ===========================================================================
async def _seed_snapshots(session):
    snapshots = [
        # Student 1 (张三) - 2 snapshots
        StudentSnapshot(id=1, student_id=1, snapshot_date=date(2026, 6, 15),
                        kp_mastery_json=json.dumps({
                            "分数通分": 0.72, "分数概念": 0.80, "异分母分数加减": 0.58,
                            "同分母分数加减": 0.88, "分数比较": 0.75
                        }, ensure_ascii=False),
                        ability_radar_json=json.dumps({
                            "概念理解能力": 78, "运算能力": 72, "应用建模能力": 65,
                            "逻辑推理能力": 80, "表达规范能力": 75
                        }, ensure_ascii=False),
                        error_causes_json=json.dumps([
                            {"cause": "概念混淆", "count": 3},
                            {"cause": "计算失误", "count": 2}
                        ], ensure_ascii=False),
                        trend="down"),
        StudentSnapshot(id=2, student_id=1, snapshot_date=date(2026, 7, 15),
                        kp_mastery_json=json.dumps({
                            "分数通分": 0.85, "分数概念": 0.88, "异分母分数加减": 0.78,
                            "同分母分数加减": 0.92, "分数比较": 0.85, "分数应用题建模": 0.72
                        }, ensure_ascii=False),
                        ability_radar_json=json.dumps({
                            "概念理解能力": 85, "运算能力": 82, "应用建模能力": 78,
                            "逻辑推理能力": 86, "表达规范能力": 83
                        }, ensure_ascii=False),
                        error_causes_json=json.dumps([
                            {"cause": "计算失误", "count": 1},
                            {"cause": "概念混淆", "count": 1}
                        ], ensure_ascii=False),
                        trend="up"),
        # Student 3 (王五) - 2 snapshots
        StudentSnapshot(id=3, student_id=3, snapshot_date=date(2026, 6, 15),
                        kp_mastery_json=json.dumps({
                            "异分母分数加减": 0.48, "分数概念": 0.62, "同分母分数加减": 0.70,
                            "分数比较": 0.55, "分数应用题建模": 0.40
                        }, ensure_ascii=False),
                        ability_radar_json=json.dumps({
                            "概念理解能力": 55, "运算能力": 60, "应用建模能力": 42,
                            "逻辑推理能力": 52, "表达规范能力": 58
                        }, ensure_ascii=False),
                        error_causes_json=json.dumps([
                            {"cause": "概念混淆", "count": 5},
                            {"cause": "建模失败", "count": 3},
                            {"cause": "计算失误", "count": 2}
                        ], ensure_ascii=False),
                        trend="down"),
        StudentSnapshot(id=4, student_id=3, snapshot_date=date(2026, 7, 15),
                        kp_mastery_json=json.dumps({
                            "异分母分数加减": 0.52, "分数概念": 0.65, "同分母分数加减": 0.72,
                            "分数比较": 0.58, "分数应用题建模": 0.45, "分数方程": 0.55
                        }, ensure_ascii=False),
                        ability_radar_json=json.dumps({
                            "概念理解能力": 58, "运算能力": 62, "应用建模能力": 48,
                            "逻辑推理能力": 55, "表达规范能力": 60
                        }, ensure_ascii=False),
                        error_causes_json=json.dumps([
                            {"cause": "概念混淆", "count": 4},
                            {"cause": "建模失败", "count": 2},
                            {"cause": "计算失误", "count": 1}
                        ], ensure_ascii=False),
                        trend="down"),
        # Student 19 (李十一) - 1 snapshot
        StudentSnapshot(id=5, student_id=19, snapshot_date=date(2026, 7, 16),
                        kp_mastery_json=json.dumps({
                            "分数加减": 0.48, "通分": 0.42, "分数概念": 0.55,
                            "同分母分数加减": 0.62, "异分母分数加减": 0.38
                        }, ensure_ascii=False),
                        ability_radar_json=json.dumps({
                            "概念理解能力": 48, "运算能力": 42, "应用建模能力": 35,
                            "逻辑推理能力": 50, "表达规范能力": 45
                        }, ensure_ascii=False),
                        error_causes_json=json.dumps([
                            {"cause": "概念混淆", "count": 6},
                            {"cause": "计算失误", "count": 3},
                            {"cause": "审题偏差", "count": 2}
                        ], ensure_ascii=False),
                        trend="down"),
    ]
    session.add_all(snapshots)


# ===========================================================================
# Additional Question Sources
# ===========================================================================
async def _seed_question_sources_extra(session):
    sources = [
        QuestionSource(id=2, name="学科网", status="running",
                       priority="local_first", on_demand=True,
                       scheduled_sync=True, fallback=True,
                       schedule="每日 03:00", min_pool=50,
                       last_sync="昨天 03:00", mapping_coverage=88,
                       quality_pass_rate=90),
        QuestionSource(id=3, name="菁优网", status="stopped",
                       priority="manual_only", on_demand=False,
                       scheduled_sync=False, fallback=False,
                       schedule="手动触发", min_pool=20,
                       last_sync="7月14日 09:30", mapping_coverage=75,
                       quality_pass_rate=85),
        QuestionSource(id=4, name="本校自建题库", status="running",
                       priority="local_first", on_demand=True,
                       scheduled_sync=False, fallback=True,
                       schedule="手动导入", min_pool=100,
                       last_sync="今天 08:00", mapping_coverage=100,
                       quality_pass_rate=98),
    ]
    session.add_all(sources)


# ===========================================================================
# Additional Source Operations
# ===========================================================================
async def _seed_source_operations_extra(session):
    ops = [
        SourceOperation(id=5, source_id=2, time="昨天 03:00", type="增量搬运",
                        detail="学科网新增28题，入库22题，6题进入待处理", status="完成"),
        SourceOperation(id=6, source_id=2, time="今天 10:30", type="老师出题调用",
                        detail="张老师 \u00b7 周九 \u00b7 百分数应用 \u00b7 自动匹配8题", status="完成"),
        SourceOperation(id=7, source_id=3, time="7月14日 09:30", type="手动同步",
                        detail="赵教研手动从菁优网拉取初中物理题目15题", status="完成"),
        SourceOperation(id=8, source_id=4, time="今天 08:00", type="批量导入",
                        detail="超级管理员导入本校历年真题120题", status="完成"),
        SourceOperation(id=9, source_id=1, time="今天 17:00", type="质量审查",
                        detail="AI自动审查教研云待处理题目，通过率92%", status="完成"),
    ]
    session.add_all(ops)


# ===========================================================================
# External candidate questions (待处理)
# ===========================================================================
async def _seed_external_candidates(session):
    questions = [
        Question(id=12, title="某商店进价200元的商品按25%利润定价后打九折，求实际利润率", type="应用题",
                 subject="数学", grade="六年级", difficulty=3,
                 kp_name="百分数应用", kp_id=12, source="学科网",
                 external_id="XKW-M-202607-501", sync_status="待处理"),
        Question(id=13, title="计算并联电路中总电阻：R1=6Ω, R2=12Ω, 求总电阻和总电流(U=12V)", type="计算题",
                 subject="物理", grade="初二", difficulty=2,
                 kp_name="串并联电路", kp_id=67, source="学科网",
                 external_id="XKW-P-202607-502", sync_status="待处理"),
        Question(id=14, title="写出盐酸与氢氧化钠反应的化学方程式并判断反应类型", type="填空题",
                 subject="化学", grade="初三", difficulty=2,
                 kp_name="酸碱盐", kp_id=87, source="菁优网",
                 external_id="JYW-C-202607-101", sync_status="待处理"),
        Question(id=15, title="已知一次函数y=2x-3与y=-x+6，求两直线交点坐标", type="解答题",
                 subject="数学", grade="初二", difficulty=2,
                 kp_name="一次函数", kp_id=41, source="菁优网",
                 external_id="JYW-M-202607-102", sync_status="待处理"),
        Question(id=16, title="设计实验验证阿基米德原理，写出实验步骤和预期结论", type="开放题",
                 subject="物理", grade="初二", difficulty=3,
                 kp_name="浮力", kp_id=63, source="学科网",
                 external_id="XKW-P-202607-503", sync_status="待处理"),
    ]
    session.add_all(questions)


# ===========================================================================
# Main entry point
# ===========================================================================
async def _seed_ai_config(session):
    """Seed default AI provider configurations."""
    from models.ai_config import AIConfig

    existing = await session.execute(select(AIConfig).limit(1))
    if existing.scalar_one_or_none():
        return  # Already seeded

    configs = [
        AIConfig(provider="mock", model_name="Mock AI", api_key="", base_url="",
                 description="本地模拟AI（开发测试用）", is_active=False, settings_json='{"delay_min":1.0,"delay_max":2.5}'),
        AIConfig(provider="zhipu", model_name="glm-4v", api_key="10822a2f88a04424b33fc72d242ac154.dUYAlJQ8GgVn9N19",
                 base_url="https://open.bigmodel.cn/api/paas/v4",
                 description="智谱GLM-4V（国产多模态·图片识别）", is_active=True,
                 settings_json='{"temperature":0.3,"max_tokens":3000}'),
        AIConfig(provider="deepseek", model_name="deepseek-chat",
                 api_key="sk-ddb80370fc1d44008d3bc934031c9fb9",
                 base_url="https://api.deepseek.com/v1",
                 description="DeepSeek（文本分析·数据诊断）", is_active=True,
                 settings_json='{"temperature":0.7,"max_tokens":2000}'),
        AIConfig(provider="openai", model_name="gpt-4o", api_key="", base_url="https://api.openai.com/v1",
                 description="OpenAI GPT-4o（视觉识别+分析）", is_active=False, settings_json='{"temperature":0.7,"max_tokens":2000}'),
        AIConfig(provider="claude", model_name="claude-3-opus-20240229", api_key="", base_url="https://api.anthropic.com",
                 description="Anthropic Claude 3（教育领域优化）", is_active=False, settings_json='{"temperature":0.5,"max_tokens":3000}'),
        AIConfig(provider="paddle", model_name="PaddleOCR", api_key="", base_url="",
                 description="百度PaddleOCR + 文心一言", is_active=False, settings_json='{}'),
        AIConfig(provider="qwen", model_name="qwen-vl-max", api_key="", base_url="https://dashscope.aliyuncs.com/api/v1",
                 description="通义千问VL（阿里云）", is_active=False, settings_json='{}'),
    ]
    for c in configs:
        session.add(c)
    print("[seed] AI config seeded with 6 providers (mock active).")


async def _reset_sequences(session):
    """Reset PostgreSQL autoincrement sequences after inserting explicit IDs.
    This prevents 'duplicate key value violates unique constraint' errors
    when the API tries to INSERT without specifying an ID.
    Only runs for PostgreSQL; SQLite manages this automatically.
    """
    from config import settings
    if not settings.DATABASE_URL.startswith("postgresql"):
        return

    tables_with_serial = [
        "grades", "classes", "users", "teacher_classes",
        "students", "tasks", "task_classes",
        "knowledge_points", "questions", "question_sources",
        "source_operations", "question_results", "exercise_plans",
        "audit_logs", "student_snapshots", "ai_configs", "error_logs",
    ]
    for table in tables_with_serial:
        try:
            await session.execute(
                text(f"SELECT setval('{table}_id_seq', (SELECT COALESCE(MAX(id), 1) FROM {table}))")
            )
        except Exception:
            pass  # Table or sequence might not exist yet


async def seed_all():
    """Seed all data if the database is empty."""
    async with async_session_factory() as session:
        if await _is_seeded(session):
            print("[seed] Database already seeded, skipping.")
            return

        print("[seed] Seeding database with Demo data...")

        # Order matters due to foreign keys - flush after each step
        await _seed_grades(session); await session.flush()
        await _seed_classes(session); await session.flush()
        await _seed_users(session); await session.flush()
        await _seed_teacher_classes(session); await session.flush()
        await _seed_students(session); await session.flush()
        await _seed_tasks(session); await session.flush()
        await _seed_task_classes(session); await session.flush()
        await _seed_knowledge_tree(session); await session.flush()
        await _seed_questions(session); await session.flush()
        await _seed_question_sources(session); await session.flush()
        await _seed_question_sources_extra(session); await session.flush()
        await _seed_source_operations(session); await session.flush()
        await _seed_source_operations_extra(session); await session.flush()
        await _seed_external_candidates(session); await session.flush()
        await _seed_question_results(session); await session.flush()
        await _seed_question_results_extra(session); await session.flush()
        await _seed_exercise_plans(session); await session.flush()
        await _seed_audit_logs(session); await session.flush()
        await _seed_snapshots(session); await session.flush()
        await _seed_ai_config(session); await session.flush()
        await _reset_sequences(session); await session.flush()

        await session.commit()
        print("[seed] Database seeded successfully with all Demo data!")
