from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime
import bson
import csv
import io
import traceback

from models.auth import UserCreate, UserUpdate, UserResponse, UserInDB
from core.security import get_password_hash
from core.deps import get_current_user, require_roles
from db.database import users_collection, enrollments_collection, classes_collection

router = APIRouter(
    prefix="/users",
    tags=["users"],
    redirect_slashes=False,
)

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    if user_data.role == "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Students must be created from the Students page"
        )

    # Teachers can only create other teachers, not admins
    if current_user.role == "teacher" and user_data.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create admin users"
        )

    existing = await users_collection.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    try:
        user_doc = {
            "email": user_data.email,
            "password_hash": get_password_hash(user_data.password),
            "full_name": user_data.full_name,
            "role": user_data.role,
            "class_id": None,
            "roll_no": None,
            "is_active": True,
            "created_by": bson.ObjectId(current_user.id),
            "created_at": datetime.utcnow(),
            "updated_at": None,
        }

        result = await users_collection.insert_one(user_doc)

        return UserResponse(
            id=str(result.inserted_id),
            email=user_doc["email"],
            full_name=user_doc["full_name"],
            role=user_doc["role"],
            class_id=None,
            roll_no=None,
            is_active=user_doc["is_active"],
            created_at=user_doc["created_at"],
        )
    except Exception as e:
        print(f"[ERROR] create_user failed: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

@router.get("/", response_model=List[UserResponse])
async def list_users(
    role: Optional[str] = None,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    # Users page only shows admin/teacher, never students
    query = {"role": {"$ne": "student"}}
    if role and role != "student":
        query["role"] = role

    users = await users_collection.find(query).to_list(length=None)
    return [
        UserResponse(
            id=str(u["_id"]),
            email=u["email"],
            full_name=u["full_name"],
            role=u["role"],
            class_id=str(u["class_id"]) if u.get("class_id") else None,
            roll_no=u.get("roll_no"),
            is_active=u.get("is_active", True),
            created_at=u["created_at"],
        )
        for u in users
    ]

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    update_data: UserUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    existing_user = await users_collection.find_one({"_id": bson.ObjectId(user_id)})
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Cannot manage students from this endpoint
    if existing_user["role"] == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students must be managed from the Students page"
        )

    # Teachers can only manage other teachers, not admins
    if current_user.role == "teacher" and existing_user["role"] == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage admin users"
        )

    update_dict = update_data.dict(exclude_unset=True)
    # Prevent changing role to student
    if update_dict.get("role") == "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change role to student from this endpoint"
        )

    # Prevent deactivating admin users - at least one admin must remain active
    if update_dict.get("is_active") is False and existing_user["role"] == "admin":
        active_admin_count = await users_collection.count_documents({"role": "admin", "is_active": True})
        if existing_user.get("is_active", True) and active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last active admin. Create another admin first or reactivate an existing admin."
            )

    if not update_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided")

    update_dict["updated_at"] = datetime.utcnow()

    result = await users_collection.find_one_and_update(
        {"_id": bson.ObjectId(user_id)},
        {"$set": update_dict},
        return_document=True
    )

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

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

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: UserResponse = Depends(require_roles("admin"))
):
    existing_user = await users_collection.find_one({"_id": bson.ObjectId(user_id)})
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if existing_user["role"] == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students must be deleted from the Students page"
        )

    # Prevent deleting the last admin (active or inactive)
    if existing_user["role"] == "admin":
        admin_count = await users_collection.count_documents({"role": "admin"})
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last admin. Create another admin first."
            )

    result = await users_collection.delete_one({"_id": bson.ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_students_csv(
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be CSV")

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    required_columns = {"email", "full_name", "password"}
    if not required_columns.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV must contain columns: {', '.join(required_columns)}"
        )

    created_users = []
    errors = []

    for row_num, row in enumerate(reader, start=2):
        try:
            existing = await users_collection.find_one({"email": row["email"]})
            if existing:
                errors.append(f"Row {row_num}: Email {row['email']} already exists")
                continue

            user_doc = {
                "email": row["email"],
                "password_hash": get_password_hash(row["password"]),
                "full_name": row["full_name"],
                "role": "student",
                "class_id": bson.ObjectId(row["class_id"]) if row.get("class_id") else None,
                "roll_no": row.get("roll_no"),
                "is_active": True,
                "created_by": bson.ObjectId(current_user.id),
                "created_at": datetime.utcnow(),
                "updated_at": None,
            }

            result = await users_collection.insert_one(user_doc)
            user_id = str(result.inserted_id)

            if user_doc["class_id"] and user_doc["roll_no"]:
                await enrollments_collection.insert_one({
                    "student_id": user_id,
                    "class_id": row["class_id"],
                    "roll_no": user_doc["roll_no"],
                    "enrolled_at": datetime.utcnow(),
                    "is_active": True,
                })

            created_users.append({
                "id": user_id,
                "email": user_doc["email"],
                "full_name": user_doc["full_name"],
            })

        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")

    return {
        "created": created_users,
        "errors": errors,
        "total_processed": len(created_users) + len(errors),
        "success_count": len(created_users),
        "error_count": len(errors),
    }

@router.get("/sample-csv")
async def download_sample_csv(
    current_user: UserResponse = Depends(require_roles("admin", "teacher"))
):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "full_name", "password", "class_id", "roll_no"])
    writer.writerow(["john@example.com", "John Doe", "password123", "CLASS_ID_HERE", "01"])
    writer.writerow(["jane@example.com", "Jane Smith", "password456", "CLASS_ID_HERE", "02"])
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sample_students.csv"},
    )
