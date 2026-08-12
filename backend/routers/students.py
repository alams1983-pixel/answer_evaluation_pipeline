from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime
import bson

from models.auth import UserCreate, UserUpdate, UserResponse
from models.gradings import GradingResponse
from core.security import get_password_hash
from core.deps import get_current_user, require_roles
from db.database import users_collection, enrollments_collection, gradings_collection

router = APIRouter(
    prefix="/students",
    tags=["students"],
    redirect_slashes=False,
)

@router.get("/", response_model=List[UserResponse])
async def list_students(
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    query = {"role": "student"}
    students = await users_collection.find(query).to_list(length=None)
    return [
        UserResponse(
            id=str(s["_id"]),
            email=s["email"],
            full_name=s["full_name"],
            role=s["role"],
            class_id=str(s["class_id"]) if s.get("class_id") else None,
            roll_no=s.get("roll_no"),
            is_active=s.get("is_active", True),
            created_at=s["created_at"],
        )
        for s in students
    ]

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_data: UserCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    if student_data.role != "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint only creates students"
        )

    existing = await users_collection.find_one({"email": student_data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    student_doc = {
        "email": student_data.email,
        "password_hash": get_password_hash(student_data.password),
        "full_name": student_data.full_name,
        "role": "student",
        "class_id": bson.ObjectId(student_data.class_id) if student_data.class_id else None,
        "roll_no": student_data.roll_no,
        "is_active": True,
        "created_by": bson.ObjectId(current_user.id),
        "created_at": datetime.utcnow(),
        "updated_at": None,
    }

    result = await users_collection.insert_one(student_doc)

    if student_doc["class_id"] and student_doc["roll_no"]:
        await enrollments_collection.insert_one({
            "student_id": str(result.inserted_id),
            "class_id": student_data.class_id,
            "roll_no": student_doc["roll_no"],
            "enrolled_at": datetime.utcnow(),
            "is_active": True,
        })

    return UserResponse(
        id=str(result.inserted_id),
        email=student_doc["email"],
        full_name=student_doc["full_name"],
        role=student_doc["role"],
        class_id=str(student_doc["class_id"]) if student_doc["class_id"] else None,
        roll_no=student_doc["roll_no"],
        is_active=student_doc["is_active"],
        created_at=student_doc["created_at"],
    )

@router.patch("/{student_id}", response_model=UserResponse)
async def update_student(
    student_id: str,
    update_data: UserUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    existing_student = await users_collection.find_one({"_id": bson.ObjectId(student_id)})
    if not existing_student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if existing_student["role"] != "student":
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

    if "password" in update_dict:
        update_dict["password_hash"] = get_password_hash(update_dict.pop("password"))

    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided")

    update_dict["updated_at"] = datetime.utcnow()

    result = await users_collection.find_one_and_update(
        {"_id": bson.ObjectId(student_id)},
        {"$set": update_dict},
        return_document=True
    )

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    return UserResponse(
        id=str(result["_id"]),
        email=result["email"],
        full_name=result["full_name"],
        role=result["role"],
        class_id=str(result["class_id"]) if result.get("class_id") else None,
        roll_no=result.get("roll_no"),
        is_active=result.get("is_active", True),
        created_at=result["created_at"],
    )

@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: str,
    current_user: UserResponse = Depends(require_roles("admin"))
):
    existing_student = await users_collection.find_one({"_id": bson.ObjectId(student_id)})
    if not existing_student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if existing_student["role"] != "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint only deletes students"
        )

    result = await users_collection.delete_one({"_id": bson.ObjectId(student_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    await enrollments_collection.delete_many({"student_id": student_id})


@router.get("/me/gradings/", response_model=List[GradingResponse])
async def get_my_gradings(
    current_user: UserResponse = Depends(get_current_user),
):
    if current_user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students only")

    gradings = await gradings_collection.find(
        {
            "student_id": bson.ObjectId(current_user.id),
            "status": "published",
        }
    ).sort("created_at", -1).to_list(length=None)

    return [
        GradingResponse(
            id=str(g["_id"]),
            sheet_id=str(g["sheet_id"]),
            exam_id=str(g["exam_id"]),
            batch_id=str(g["batch_id"]),
            result_schema_id=str(g["result_schema_id"]) if g.get("result_schema_id") else None,
            result=g.get("result", {}),
            total_awarded=g.get("total_awarded", 0),
            total_max=g.get("total_max", 0),
            status=g.get("status", "auto"),
            reviewed_by=str(g["reviewed_by"]) if g.get("reviewed_by") else None,
            reviewed_at=g.get("reviewed_at"),
            published_at=g.get("published_at"),
            override_log=g.get("override_log", []),
            created_at=g["created_at"],
        )
        for g in gradings
    ]
