from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
import bson

from models.auth import UserResponse
from models.school import SubjectCreate, SubjectUpdate, SubjectResponse
from core.deps import get_current_user, require_roles
from db.database import subjects_collection, classes_collection

router = APIRouter(
    prefix="/subjects",
    tags=["subjects"],
    redirect_slashes=False,
)

@router.get("/", response_model=List[SubjectResponse])
async def list_subjects(
    class_id: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    query = {}
    if class_id:
        query["class_id"] = class_id

    if current_user.role == "teacher":
        teacher_classes = await classes_collection.find({"teacher_ids": current_user.id}).to_list(length=None)
        class_ids = [str(c["_id"]) for c in teacher_classes]
        query["class_id"] = {"$in": class_ids} if class_id and class_id in class_ids else {"$in": class_ids}

    subjects = await subjects_collection.find(query).to_list(length=None)
    return [
        SubjectResponse(
            id=str(s["_id"]),
            name=s["name"],
            code=s.get("code"),
            class_id=s["class_id"],
            teacher_ids=s.get("teacher_ids", []),
            created_by=str(s["created_by"]) if s.get("created_by") else None,
            created_at=s["created_at"],
            updated_at=s.get("updated_at"),
        )
        for s in subjects
    ]

@router.post("/", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    subject_data: SubjectCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    existing_class = await classes_collection.find_one({"_id": bson.ObjectId(subject_data.class_id)})
    if not existing_class:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    if current_user.role == "teacher":
        if current_user.id not in existing_class.get("teacher_ids", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to add subjects to this class"
            )

    existing = await subjects_collection.find_one({
        "name": subject_data.name,
        "class_id": subject_data.class_id,
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject with this name already exists for this class"
        )

    subject_doc = {
        "name": subject_data.name,
        "code": subject_data.code,
        "class_id": subject_data.class_id,
        "teacher_ids": subject_data.teacher_ids,
        "created_by": bson.ObjectId(current_user.id),
        "created_at": datetime.utcnow(),
        "updated_at": None,
    }

    result = await subjects_collection.insert_one(subject_doc)
    subject_doc["_id"] = result.inserted_id

    return SubjectResponse(
        id=str(result.inserted_id),
        name=subject_doc["name"],
        code=subject_doc["code"],
        class_id=subject_doc["class_id"],
        teacher_ids=subject_doc["teacher_ids"],
        created_by=current_user.id,
        created_at=subject_doc["created_at"],
        updated_at=subject_doc["updated_at"],
    )

@router.patch("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: str,
    update_data: SubjectUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    existing_subject = await subjects_collection.find_one({"_id": bson.ObjectId(subject_id)})
    if not existing_subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    if current_user.role == "teacher":
        teacher_classes = await classes_collection.find({"teacher_ids": current_user.id}).to_list(length=None)
        class_ids = [str(c["_id"]) for c in teacher_classes]
        if existing_subject["class_id"] not in class_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to manage this subject"
            )

    update_dict = update_data.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided")

    update_dict["updated_at"] = datetime.utcnow()

    result = await subjects_collection.find_one_and_update(
        {"_id": bson.ObjectId(subject_id)},
        {"$set": update_dict},
        return_document=True
    )

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    return SubjectResponse(
        id=str(result["_id"]),
        name=result["name"],
        code=result.get("code"),
        class_id=result["class_id"],
        teacher_ids=result.get("teacher_ids", []),
        created_by=str(result["created_by"]) if result.get("created_by") else None,
        created_at=result["created_at"],
        updated_at=result.get("updated_at"),
    )

@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: str,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    existing_subject = await subjects_collection.find_one({"_id": bson.ObjectId(subject_id)})
    if not existing_subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    if current_user.role == "teacher":
        teacher_classes = await classes_collection.find({"teacher_ids": current_user.id}).to_list(length=None)
        class_ids = [str(c["_id"]) for c in teacher_classes]
        if existing_subject["class_id"] not in class_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this subject"
            )

    result = await subjects_collection.delete_one({"_id": bson.ObjectId(subject_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")