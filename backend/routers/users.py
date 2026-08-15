from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import List, Optional
from datetime import datetime
import csv
import io
import traceback

from models.auth import UserCreate, UserUpdate, UserResponse
from core.security import get_password_hash
from core.deps import get_current_user, require_roles
from db.database import get_db
from db.models import User, Enrollment, Class

router = APIRouter(
    prefix="/users",
    tags=["users"],
    redirect_slashes=False,
)

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    if user_data.role == "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Students must be created from the Students page"
        )

    if current_user.role == "teacher" and user_data.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create admin users"
        )

    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    try:
        user = User(
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role,
            class_id=None,
            roll_no=None,
            is_active=True,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        return UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            class_id=None,
            roll_no=None,
            is_active=user.is_active,
            created_at=user.created_at,
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
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.role != "student")
    if role and role != "student":
        query = query.where(User.role == role)

    result = await db.execute(query)
    users = result.scalars().all()

    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            class_id=str(u.class_id) if u.class_id else None,
            roll_no=u.roll_no,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    update_data: UserUpdate,
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    existing_user = result.scalar_one_or_none()

    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if existing_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students must be managed from the Students page"
        )

    if current_user.role == "teacher" and existing_user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage admin users"
        )

    update_dict = update_data.dict(exclude_unset=True)
    if update_dict.get("role") == "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change role to student from this endpoint"
        )

    if update_dict.get("is_active") is False and existing_user.role == "admin":
        count_res = await db.execute(
            select(func.count(User.id)).where(User.role == "admin", User.is_active == True)
        )
        active_admin_count = count_res.scalar()
        if existing_user.is_active and active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last active admin. Create another admin first or reactivate an existing admin."
            )

    if "full_name" in update_dict:
        existing_user.full_name = update_dict["full_name"]
    if "role" in update_dict and update_dict["role"]:
        existing_user.role = update_dict["role"]
    if "is_active" in update_dict and update_dict["is_active"] is not None:
        existing_user.is_active = update_dict["is_active"]
    if "password" in update_dict and update_dict["password"]:
        existing_user.password_hash = get_password_hash(update_dict["password"])

    existing_user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(existing_user)

    return UserResponse(
        id=str(existing_user.id),
        email=existing_user.email,
        full_name=existing_user.full_name,
        role=existing_user.role,
        class_id=str(existing_user.class_id) if existing_user.class_id else None,
        roll_no=existing_user.roll_no,
        is_active=existing_user.is_active,
        created_at=existing_user.created_at,
    )

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: UserResponse = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    existing_user = result.scalar_one_or_none()

    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if existing_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students must be deleted from the Students page"
        )

    if existing_user.role == "admin":
        count_res = await db.execute(select(func.count(User.id)).where(User.role == "admin"))
        admin_count = count_res.scalar()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last admin. Create another admin first."
            )

    await db.delete(existing_user)
    await db.commit()

@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_students_csv(
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db)
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

    # Build Class Lookup Map
    res_cls = await db.execute(select(Class))
    existing_classes = res_cls.scalars().all()
    class_map = {}
    for cls in existing_classes:
        c_id = str(cls.id)
        class_map[c_id.lower()] = c_id
        class_map[cls.name.strip().lower()] = c_id
        if cls.section:
            class_map[f"{cls.name} - {cls.section}".strip().lower()] = c_id
            class_map[f"{cls.name} {cls.section}".strip().lower()] = c_id
            class_map[f"{cls.name}{cls.section}".strip().lower()] = c_id

    created_users = []
    errors = []

    placeholders = {"CLASS_ID_HERE", "YOUR_CLASS_ID", "CLASS_ID", "NONE", "NULL", "SELECT_CLASS", "OPTIONAL"}

    for row_num, row in enumerate(reader, start=2):
        try:
            email = (row.get("email") or "").strip()
            full_name = (row.get("full_name") or "").strip()
            password = (row.get("password") or "").strip()
            raw_class_id = (row.get("class_id") or "").strip()
            roll_no = (row.get("roll_no") or "").strip() or None

            if not email or not full_name or not password:
                errors.append(f"Row {row_num}: Missing required fields (email, full_name, or password)")
                continue

            res = await db.execute(select(User).where(User.email == email))
            if res.scalar_one_or_none():
                errors.append(f"Row {row_num}: Email '{email}' already exists")
                continue

            matched_class_id = None
            if raw_class_id and raw_class_id.upper() not in placeholders:
                matched_class_id = class_map.get(raw_class_id.lower())
                if not matched_class_id:
                    # Check direct UUID lookup
                    res_c = await db.execute(select(Class).where(Class.id == raw_class_id))
                    c_obj = res_c.scalar_one_or_none()
                    if c_obj:
                        matched_class_id = str(c_obj.id)
                    else:
                        errors.append(f"Row {row_num}: Class '{raw_class_id}' not found. Please create class first or leave class_id empty.")
                        continue

            user = User(
                email=email,
                password_hash=get_password_hash(password),
                full_name=full_name,
                role="student",
                class_id=matched_class_id,
                roll_no=roll_no,
                is_active=True,
                created_by=current_user.id,
                created_at=datetime.utcnow(),
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            if user.class_id and user.roll_no:
                enrollment = Enrollment(
                    student_id=user.id,
                    class_id=user.class_id,
                    roll_no=user.roll_no,
                    enrolled_at=datetime.utcnow(),
                    is_active=True,
                )
                db.add(enrollment)
                await db.commit()

            created_users.append({
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
            })

        except Exception as e:
            await db.rollback()
            clean_err = str(e)
            if "foreign key constraint fails" in clean_err.lower():
                clean_err = f"Invalid Class ID '{row.get('class_id')}' specified. Class does not exist."
            errors.append(f"Row {row_num}: {clean_err}")

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
