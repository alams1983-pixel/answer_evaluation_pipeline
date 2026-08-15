from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.security import decode_token
from models.auth import UserResponse
from db.database import get_db, AsyncSessionLocal
from db.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    payload = decode_token(token)
    email = payload.get("sub")
    user_id = payload.get("user_id")

    if email is None or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user and email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        class_id=str(user.class_id) if user.class_id else None,
        roll_no=user.roll_no,
        is_active=user.is_active,
        created_at=user.created_at,
    )


async def get_current_user_optional(
    request: Request,
) -> Optional[UserResponse]:
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.query_params.get("token")

    if not token:
        return None

    try:
        payload = decode_token(token)
        email = payload.get("sub")
        user_id = payload.get("user_id")

        if email is None or user_id is None:
            return None

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user and email:
                result = await db.execute(select(User).where(User.email == email))
                user = result.scalar_one_or_none()

            if not user or not user.is_active:
                return None

            return UserResponse(
                id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                class_id=str(user.class_id) if user.class_id else None,
                roll_no=user.roll_no,
                is_active=user.is_active,
                created_at=user.created_at,
            )
    except Exception:
        return None


def require_roles(*allowed_roles: str):
    async def role_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' not permitted",
            )
        return current_user
    return role_checker
