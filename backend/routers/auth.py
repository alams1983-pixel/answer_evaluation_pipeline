from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets
import hashlib

from core.security import get_password_hash, verify_password, create_access_token
from core.deps import get_current_user
from db.database import get_db
from db.models import User, PasswordReset
from models.auth import (
    UserLogin, UserResponse, Token, PasswordResetRequest,
    PasswordResetConfirm, ChangePasswordRequest
)

router = APIRouter(prefix="/auth", tags=["Authentication"], redirect_slashes=False)


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated",
        )

    token_data = {
        "sub": user.email,
        "user_id": str(user.id),
        "role": user.role,
    }
    access_token = create_access_token(data=token_data)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return current_user


@router.post("/forgot-password")
async def forgot_password(request: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    """Generate a password reset token."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user:
        return {"message": "If the email exists, a reset token has been generated."}

    reset_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=30)

    reset_record = PasswordReset(
        user_id=user.id,
        token=token_hash,
        expires_at=expires_at,
        created_at=datetime.utcnow(),
    )
    db.add(reset_record)
    await db.commit()

    return {
        "message": "If the email exists, a reset token has been generated.",
        "token": reset_token,
        "expires_in_minutes": 30,
    }


@router.post("/reset-password")
async def reset_password(request: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    """Reset password using a valid reset token."""
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()
    result = await db.execute(select(PasswordReset).where(PasswordReset.token == token_hash))
    reset_record = result.scalar_one_or_none()

    if not reset_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if reset_record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )

    result = await db.execute(select(User).where(User.id == reset_record.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = get_password_hash(request.new_password)
    user.updated_at = datetime.utcnow()

    await db.delete(reset_record)
    await db.commit()

    return {"message": "Password reset successfully"}


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change password for authenticated user."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    user.password_hash = get_password_hash(request.new_password)
    user.updated_at = datetime.utcnow()
    await db.commit()

    return {"message": "Password changed successfully"}
