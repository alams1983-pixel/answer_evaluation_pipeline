from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime

from models.auth import UserResponse
from models.school import ClassCreate, ClassUpdate, ClassResponse
from core.deps import get_current_user, require_roles
from db.database import get_db
from db.models import Class

router = APIRouter(
    prefix="/classes",
    tags=["classes"],
    redirect_slashes=False,
)

@router.get("/", response_model=List[ClassResponse])
async def list_classes(
    session: str | None = None,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Class)
    if session:
        query = query.where(Class.session == session)

    result = await db.execute(query)
    classes = result.scalars().all()

    return [
        ClassResponse(
            id=str(c.id),
            name=c.name,
            session=c.session or "",
            section=c.section,
            teacher_ids=[],
            class_teacher_id=c.class_teacher_id,
            created_by=str(c.created_by) if c.created_by else None,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in classes
    ]

@router.post("/", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    class_data: ClassCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    query = select(Class).where(
        Class.name == class_data.name,
        Class.section == class_data.section,
        Class.session == class_data.session,
    )
    res = await db.execute(query)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A class '{class_data.name}' with section '{class_data.section or 'N/A'}' already exists for session '{class_data.session}'"
        )

    new_class = Class(
        name=class_data.name,
        section=class_data.section,
        session=class_data.session,
        class_teacher_id=class_data.class_teacher_id,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(new_class)
    await db.commit()
    await db.refresh(new_class)

    return ClassResponse(
        id=str(new_class.id),
        name=new_class.name,
        section=new_class.section,
        session=new_class.session,
        teacher_ids=class_data.teacher_ids or [],
        class_teacher_id=new_class.class_teacher_id,
        created_by=current_user.id,
        created_at=new_class.created_at,
        updated_at=new_class.updated_at,
    )

@router.patch("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: str,
    update_data: ClassUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Class).where(Class.id == class_id))
    existing_class = res.scalar_one_or_none()
    if not existing_class:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    update_dict = update_data.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided")

    if "name" in update_dict:
        existing_class.name = update_dict["name"]
    if "session" in update_dict:
        existing_class.session = update_dict["session"]
    if "section" in update_dict:
        existing_class.section = update_dict["section"]
    if "class_teacher_id" in update_dict:
        existing_class.class_teacher_id = update_dict["class_teacher_id"]

    existing_class.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(existing_class)

    return ClassResponse(
        id=str(existing_class.id),
        name=existing_class.name,
        section=existing_class.section,
        session=existing_class.session,
        teacher_ids=update_data.teacher_ids or [],
        class_teacher_id=existing_class.class_teacher_id,
        created_by=str(existing_class.created_by) if existing_class.created_by else None,
        created_at=existing_class.created_at,
        updated_at=existing_class.updated_at,
    )

@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: str,
    current_user: UserResponse = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Class).where(Class.id == class_id))
    existing_class = res.scalar_one_or_none()
    if not existing_class:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    await db.delete(existing_class)
    await db.commit()