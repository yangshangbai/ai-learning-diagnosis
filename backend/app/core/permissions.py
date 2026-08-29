"""共享权限 helper：教师数据隔离。

教师角色通过 TeacherClass 关联表限定可见的班级；再由其班级限定可见的学生。
管理员返回 None（全量）。
"""
from typing import List, Optional

from .. import models
from ..core.security import Principal


def teacher_visible_class_ids(db, principal: Principal) -> Optional[List[int]]:
    """返回教师可见班级 id 列表；管理员返回 None（表示无限制）。"""
    if principal is None or principal.role == "admin":
        return None
    rows = (
        db.query(models.TeacherClass)
        .filter(models.TeacherClass.teacher_id == principal.teacher_id)
        .all()
    )
    return [r.class_id for r in rows] or []
