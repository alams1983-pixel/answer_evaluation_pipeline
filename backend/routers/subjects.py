from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime

from models.auth import UserResponse
from models.school import SubjectCreate, SubjectUpdate, SubjectResponse
from core.deps import get_current_user, require_roles
from db.database import get_db
from db.models import Subject, Class

router = APIRouter(
    prefix="/subjects",
    tags=["subjects"],
    redirect_slashes=False,
)

@router.get("/", response_model=List[SubjectResponse])
async def list_subjects(
    class_id: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Subject)
    if class_id:
        query = query.where(Subject.class_id == class_id)

    result = await db.execute(query)
    subjects = result.scalars().all()

    return [
        SubjectResponse(
            id=str(s.id),
            name=s.name,
            code=s.code,
            class_id=s.class_id,
            teacher_ids=[],
            created_by=str(s.created_by) if s.created_by else None,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in subjects
    ]

@router.post("/", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    subject_data: SubjectCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Class).where(Class.id == subject_data.class_id))
    existing_class = res.scalar_one_or_none()
    if not existing_class:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    res = await db.execute(
        select(Subject).where(
            Subject.name == subject_data.name,
            Subject.class_id == subject_data.class_id,
        )
    )
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject with this name already exists for this class"
        )

    new_subject = Subject(
        name=subject_data.name,
        code=subject_data.code,
        class_id=subject_data.class_id,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(new_subject)
    await db.commit()
    await db.refresh(new_subject)

    return SubjectResponse(
        id=str(new_subject.id),
        name=new_subject.name,
        code=new_subject.code,
        class_id=new_subject.class_id,
        teacher_ids=subject_data.teacher_ids or [],
        created_by=current_user.id,
        created_at=new_subject.created_at,
        updated_at=new_subject.updated_at,
    )

@router.patch("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: str,
    update_data: SubjectUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Subject).where(Subject.id == subject_id))
    existing_subject = res.scalar_one_or_none()
    if not existing_subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    update_dict = update_data.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided")

    if "name" in update_dict:
        existing_subject.name = update_dict["name"]
    if "code" in update_dict:
        existing_subject.code = update_dict["code"]
    if "class_id" in update_dict and update_dict["class_id"]:
        existing_subject.class_id = update_dict["class_id"]

    existing_subject.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(existing_subject)

    return SubjectResponse(
        id=str(existing_subject.id),
        name=existing_subject.name,
        code=existing_subject.code,
        class_id=existing_subject.class_id,
        teacher_ids=update_data.teacher_ids or [],
        created_by=str(existing_subject.created_by) if existing_subject.created_by else None,
        created_at=existing_subject.created_at,
        updated_at=existing_subject.updated_at,
    )

@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Subject).where(Subject.id == subject_id))
    existing_subject = res.scalar_one_or_none()
    if not existing_subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    await db.delete(existing_subject)
    await db.commit()