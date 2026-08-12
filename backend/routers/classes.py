from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime
import bson

from models.auth import UserResponse
from models.school import ClassCreate, ClassUpdate, ClassResponse
from core.deps import get_current_user, require_roles
from db.database import classes_collection, users_collection

router = APIRouter(
    prefix="/classes",
    tags=["classes"],
    redirect_slashes=False,
)

@router.get("/", response_model=List[ClassResponse])
async def list_classes(
    session: str | None = None,
    current_user: UserResponse = Depends(get_current_user)
):
    query = {}
    if session:
        query["session"] = session
    if current_user.role == "teacher":
        query["teacher_ids"] = current_user.id

    classes = await classes_collection.find(query).to_list(length=None)
    return [
        ClassResponse(
            id=str(c["_id"]),
            name=c["name"],
            session=c.get("session", c.get("academic_year", "")),
            section=c.get("section"),
            teacher_ids=c.get("teacher_ids", []),
            class_teacher_id=c.get("class_teacher_id"),
            created_by=str(c["created_by"]) if c.get("created_by") else None,
            created_at=c["created_at"],
            updated_at=c.get("updated_at"),
        )
        for c in classes
    ]

@router.post("/", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    class_data: ClassCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    existing = await classes_collection.find_one({
        "name": class_data.name,
        "section": class_data.section,
        "session": class_data.session,
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A class '{class_data.name}' with section '{class_data.section or 'N/A'}' already exists for session '{class_data.session}'"
        )

    class_doc = {
        "name": class_data.name,
        "section": class_data.section,
        "session": class_data.session,
        "teacher_ids": class_data.teacher_ids,
        "class_teacher_id": class_data.class_teacher_id,
        "created_by": bson.ObjectId(current_user.id),
        "created_at": datetime.utcnow(),
        "updated_at": None,
    }

    result = await classes_collection.insert_one(class_doc)
    class_doc["_id"] = result.inserted_id

    return ClassResponse(
        id=str(result.inserted_id),
        name=class_doc["name"],
        section=class_doc["section"],
        session=class_doc["session"],
        teacher_ids=class_doc["teacher_ids"],
        class_teacher_id=class_doc["class_teacher_id"],
        created_by=current_user.id,
        created_at=class_doc["created_at"],
        updated_at=class_doc["updated_at"],
    )

@router.patch("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: str,
    update_data: ClassUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    if current_user.role == "teacher":
        existing_class = await classes_collection.find_one({"_id": bson.ObjectId(class_id)})
        if not existing_class:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
        if current_user.id not in existing_class.get("teacher_ids", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to manage this class"
            )

    update_dict = update_data.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided")

    update_dict["updated_at"] = datetime.utcnow()

    result = await classes_collection.find_one_and_update(
        {"_id": bson.ObjectId(class_id)},
        {"$set": update_dict},
        return_document=True
    )

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    return ClassResponse(
        id=str(result["_id"]),
        name=result["name"],
        section=result.get("section"),
        session=result.get("session", result.get("academic_year", "")),
        teacher_ids=result.get("teacher_ids", []),
        class_teacher_id=result.get("class_teacher_id"),
        created_by=str(result["created_by"]) if result.get("created_by") else None,
        created_at=result["created_at"],
        updated_at=result.get("updated_at"),
    )

@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: str,
    current_user: UserResponse = Depends(require_roles("admin"))
):
    result = await classes_collection.delete_one({"_id": bson.ObjectId(class_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")