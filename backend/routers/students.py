from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime

from models.auth import UserCreate, UserUpdate, UserResponse
from models.gradings import GradingResponse
from core.security import get_password_hash
from core.deps import get_current_user, require_roles
from db.database import get_db
from db.models import User, Enrollment, Grading

router = APIRouter(
    prefix="/students",
    tags=["students"],
    redirect_slashes=False,
)

@router.get("/", response_model=List[UserResponse])
async def list_students(
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.role == "student"))
    students = result.scalars().all()
    return [
        UserResponse(
            id=str(s.id),
            email=s.email,
            full_name=s.full_name,
            role=s.role,
            class_id=str(s.class_id) if s.class_id else None,
            roll_no=s.roll_no,
            is_active=s.is_active,
            created_at=s.created_at,
        )
        for s in students
    ]

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_data: UserCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    if student_data.role != "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint only creates students"
        )

    res = await db.execute(select(User).where(User.email == student_data.email))
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    student = User(
        email=student_data.email,
        password_hash=get_password_hash(student_data.password),
        full_name=student_data.full_name,
        role="student",
        class_id=student_data.class_id if student_data.class_id else None,
        roll_no=student_data.roll_no,
        is_active=True,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)

    if student.class_id and student.roll_no:
        enrollment = Enrollment(
            student_id=student.id,
            class_id=student.class_id,
            roll_no=student.roll_no,
            enrolled_at=datetime.utcnow(),
            is_active=True,
        )
        db.add(enrollment)
        await db.commit()

    return UserResponse(
        id=str(student.id),
        email=student.email,
        full_name=student.full_name,
        role=student.role,
        class_id=str(student.class_id) if student.class_id else None,
        roll_no=student.roll_no,
        is_active=student.is_active,
        created_at=student.created_at,
    )

@router.patch("/{student_id}", response_model=UserResponse)
async def update_student(
    student_id: str,
    update_data: UserUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(User).where(User.id == student_id))
    existing_student = res.scalar_one_or_none()

    if not existing_student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if existing_student.role != "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint only manages students"
        )

    update_dict = update_data.dict(exclude_unset=True)

    if update_dict.get("role") and update_dict["role"] != "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change role from student via this endpoint"
        )

    if "full_name" in update_dict:
        existing_student.full_name = update_dict["full_name"]
    if "class_id" in update_dict:
        existing_student.class_id = update_dict["class_id"]
    if "roll_no" in update_dict:
        existing_student.roll_no = update_dict["roll_no"]
    if "is_active" in update_dict and update_dict["is_active"] is not None:
        existing_student.is_active = update_dict["is_active"]
    if "password" in update_dict and update_dict["password"]:
        existing_student.password_hash = get_password_hash(update_dict["password"])

    existing_student.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(existing_student)

    return UserResponse(
        id=str(existing_student.id),
        email=existing_student.email,
        full_name=existing_student.full_name,
        role=existing_student.role,
        class_id=str(existing_student.class_id) if existing_student.class_id else None,
        roll_no=existing_student.roll_no,
        is_active=existing_student.is_active,
        created_at=existing_student.created_at,
    )

@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: str,
    current_user: UserResponse = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(User).where(User.id == student_id))
    existing_student = res.scalar_one_or_none()
    if not existing_student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if existing_student.role != "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint only deletes students"
        )

    await db.delete(existing_student)
    await db.commit()

@router.get("/me/gradings/", response_model=List[GradingResponse])
async def get_my_gradings(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students only")

    res = await db.execute(
        select(Grading)
        .where(Grading.student_id == current_user.id, Grading.status == "published")
        .order_by(Grading.created_at.desc())
    )
    gradings = res.scalars().all()

    return [
        GradingResponse(
            id=str(g.id),
            sheet_id=str(g.sheet_id),
            exam_id=str(g.exam_id),
            batch_id=str(g.batch_id),
            result_schema_id=str(g.result_schema_id) if g.result_schema_id else None,
            result=g.result or {},
            total_awarded=g.total_awarded or 0,
            total_max=g.total_max or 0,
            status=g.status or "auto",
            reviewed_by=str(g.reviewed_by) if g.reviewed_by else None,
            reviewed_at=g.reviewed_at,
            published_at=g.published_at,
            override_log=g.override_log or [],
            created_at=g.created_at,
        )
        for g in gradings
    ]
