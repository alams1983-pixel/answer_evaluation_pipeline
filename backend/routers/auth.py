from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib
from bson import ObjectId

from core.config import settings
from core.security import get_password_hash, verify_password, create_access_token
from core.deps import get_current_user
from models.auth import (
    UserCreate, UserLogin, UserResponse, UserUpdate,
    Token, PasswordResetRequest, PasswordResetConfirm, ChangePasswordRequest
)
from db.database import users_collection, password_resets_collection

router = APIRouter(prefix="/auth", tags=["Authentication"], redirect_slashes=False)


@router.post("/login", response_model=Token)
async def login(data: UserLogin):
    """Authenticate user and return JWT token."""
    user = await users_collection.find_one({"email": data.email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated",
        )

    token_data = {
        "sub": user["email"],
        "user_id": str(user["_id"]),
        "role": user["role"],
    }
    access_token = create_access_token(data=token_data)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return current_user


@router.post("/forgot-password")
async def forgot_password(request: PasswordResetRequest):
    """Generate a password reset token (visible in admin panel)."""
    user = await users_collection.find_one({"email": request.email})
    if not user:
        # For security, don't reveal if user exists
        return {"message": "If the email exists, a reset token has been generated."}

    # Generate a random token
    reset_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=30)

    # Store hashed token
    await password_resets_collection.insert_one({
        "user_id": user["_id"],
        "token_hash": token_hash,
        "expires_at": expires_at,
        "used_at": None,
        "created_at": datetime.utcnow(),
    })

    # In development, return the token directly so admin can hand it to user
    # In production, you'd send this via email (not implemented)
    return {
        "message": "If the email exists, a reset token has been generated.",
        "token": reset_token,  # Only in dev; remove in prod
        "expires_in_minutes": 30,
    }


@router.post("/reset-password")
async def reset_password(request: PasswordResetConfirm):
    """Reset password using a valid reset token."""
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()
    reset_record = await password_resets_collection.find_one({
        "token_hash": token_hash,
        "used_at": None,
    })

    if not reset_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if reset_record["expires_at"] < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )

    # Update user password
    new_hash = get_password_hash(request.new_password)
    await users_collection.update_one(
        {"_id": reset_record["user_id"]},
        {"$set": {"password_hash": new_hash, "updated_at": datetime.utcnow()}}
    )

    # Mark token as used
    await password_resets_collection.update_one(
        {"_id": reset_record["_id"]},
        {"$set": {"used_at": datetime.utcnow()}}
    )

    return {"message": "Password reset successfully"}


@router.post("/change-password")
async def change_password(request: ChangePasswordRequest, current_user: UserResponse = Depends(get_current_user)):
    """Change password for authenticated user (requires current password)."""
    user = await users_collection.find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(request.current_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    new_hash = get_password_hash(request.new_password)
    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": new_hash, "updated_at": datetime.utcnow()}}
    )

    return {"message": "Password changed successfully"}
