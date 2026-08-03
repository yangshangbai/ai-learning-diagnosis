"""Auth routes: login, current user, logout."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from database import get_db
from models.user import User
from schemas.auth import LoginRequest, TokenResponse, UserInfo
from middleware.auth_middleware import get_current_user
from services.auth_service import create_access_token, verify_password

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db=Depends(get_db)):
    """Authenticate a user and return a JWT token with user info."""
    result = await db.execute(select(User).where(User.phone == body.phone))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误",
        )

    token = create_access_token(user.id)

    # Get teacher's class IDs if role is teacher
    class_ids = []
    if user.role == "teacher":
        from models.teacher import TeacherClass
        tc_result = await db.execute(
            select(TeacherClass).where(TeacherClass.teacher_id == user.id)
        )
        class_ids = [tc.class_id for tc in tc_result.scalars().all()]

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "name": user.name,
            "role": user.role,
            "phone": user.phone,
            "avatar": user.avatar,
            "grades": json.loads(user.grades) if user.grades else [],
            "subjects": json.loads(user.subjects) if user.subjects else [],
            "classes": class_ids,
        },
    )


@router.get("/me", response_model=UserInfo)
async def get_me(current_user=Depends(get_current_user)):
    """Return the currently authenticated user's info."""
    return UserInfo(
        id=current_user.id,
        name=current_user.name,
        phone=current_user.phone,
        role=current_user.role,
        avatar=current_user.avatar or "",
        grades=json.loads(current_user.grades) if current_user.grades else [],
        subjects=json.loads(current_user.subjects) if current_user.subjects else [],
    )


@router.post("/logout")
async def logout(current_user=Depends(get_current_user)):
    """Logout (stateless JWT - just returns ok)."""
    return {"success": True, "message": "已登出"}


@router.get("/teachers")
async def list_teachers_public(db=Depends(get_db)):
    """Public endpoint: list teacher names and phones for login page convenience. No auth needed."""
    result = await db.execute(
        select(User).where(User.role.in_(["teacher", "admin", "research", "super"]))
    )
    users = result.scalars().all()
    return [
        {
            "name": u.name,
            "phone": u.phone,
            "role": u.role,
        }
        for u in users
    ]
