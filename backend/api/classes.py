"""Class CRUD routes."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func

from database import get_db
from models.class_ import Class, Grade
from models.student import Student
from schemas.class_ import ClassCreate, ClassUpdate, ClassOut, GradeCreate, GradeUpdate
from middleware.auth_middleware import get_current_user, require_admin

router = APIRouter()


@router.get("/grades")
async def list_grades(db=Depends(get_db)):
    """List all grades."""
    result = await db.execute(select(Grade).order_by(Grade.sort_order))
    grades = result.scalars().all()
    return [
        {"id": g.id, "name": g.name, "sort_order": g.sort_order} for g in grades
    ]


@router.post("/grades")
async def create_grade(
    body: GradeCreate,
    db=Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Create a new grade (admin only)."""
    grade = Grade(name=body.name, sort_order=body.sort_order)
    db.add(grade)
    await db.flush()
    return {"id": grade.id, "name": grade.name, "sort_order": grade.sort_order, "message": "创建成功"}


@router.put("/grades/{grade_id}")
async def update_grade(
    grade_id: int,
    body: GradeUpdate,
    db=Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Update a grade's name or sort_order (admin only)."""
    result = await db.execute(select(Grade).where(Grade.id == grade_id))
    grade = result.scalar_one_or_none()
    if not grade:
        raise HTTPException(status_code=404, detail="年级不存在")

    if body.name is not None:
        grade.name = body.name
    if body.sort_order is not None:
        grade.sort_order = body.sort_order

    await db.flush()
    return {"id": grade.id, "name": grade.name, "sort_order": grade.sort_order, "message": "更新成功"}


@router.delete("/grades/{grade_id}")
async def delete_grade(
    grade_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Delete a grade (admin only). Prevent deletion if classes exist under this grade."""
    result = await db.execute(select(Grade).where(Grade.id == grade_id))
    grade = result.scalar_one_or_none()
    if not grade:
        raise HTTPException(status_code=404, detail="年级不存在")

    # Check for existing classes
    from sqlalchemy import func as sql_func
    class_count_result = await db.execute(
        select(sql_func.count()).select_from(Class).where(Class.grade_id == grade_id)
    )
    class_count = class_count_result.scalar()
    if class_count > 0:
        raise HTTPException(status_code=409, detail=f"该年级下有 {class_count} 个班级，请先删除班级后再删除年级")

    await db.delete(grade)
    await db.flush()
    return {"message": "删除成功"}


@router.get("")
async def list_classes(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    grade_id: int = Query(None),
    db=Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List all classes with grade_name and student_count."""
    query = select(Class)
    count_query = select(func.count()).select_from(Class)

    if grade_id:
        query = query.where(Class.grade_id == grade_id)
        count_query = count_query.where(Class.grade_id == grade_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )
    classes = result.scalars().all()

    items = []
    for c in classes:
        # Get grade name
        grade_result = await db.execute(select(Grade).where(Grade.id == c.grade_id))
        g = grade_result.scalar_one_or_none()
        grade_name = g.name if g else ""

        # Count students
        count_result = await db.execute(
            select(func.count()).select_from(Student).where(Student.class_id == c.id)
        )
        student_count = count_result.scalar()

        items.append({
            "id": c.id,
            "name": c.name,
            "grade_id": c.grade_id,
            "grade_name": grade_name,
            "subjects": json.loads(c.subjects) if c.subjects else [],
            "student_count": student_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


@router.post("")
async def create_class(
    body: ClassCreate,
    db=Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Create a new class."""
    grade_result = await db.execute(select(Grade).where(Grade.id == body.grade_id))
    if not grade_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="年级不存在")

    cls = Class(
        name=body.name,
        grade_id=body.grade_id,
        subjects=json.dumps(body.subjects, ensure_ascii=False),
    )
    db.add(cls)
    await db.flush()

    return {"id": cls.id, "name": cls.name, "grade_id": cls.grade_id, "message": "创建成功"}


@router.put("/{class_id}")
async def update_class(
    class_id: int,
    body: ClassUpdate,
    db=Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Update a class."""
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    if body.name is not None:
        cls.name = body.name
    if body.grade_id is not None:
        cls.grade_id = body.grade_id
    if body.subjects is not None:
        cls.subjects = json.dumps(body.subjects, ensure_ascii=False)

    await db.flush()
    return {"id": cls.id, "name": cls.name, "message": "更新成功"}


@router.delete("/{class_id}")
async def delete_class(
    class_id: int,
    db=Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Delete a class. Prevent deletion if students exist."""
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    # Check for existing students
    student_count_result = await db.execute(
        select(func.count()).select_from(Student).where(Student.class_id == class_id)
    )
    student_count = student_count_result.scalar()
    if student_count > 0:
        raise HTTPException(status_code=409, detail=f"该班级下有 {student_count} 名学生，请先移除或转班后再删除")

    await db.delete(cls)
    await db.flush()
    return {"message": "删除成功"}
