from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from core.security import decode_token
from models.auth import TokenData, UserResponse
from db.database import db
import bson

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserResponse:
    payload = decode_token(token)
    email = payload.get("sub")
    user_id = payload.get("user_id")

    if email is None or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await db.users.find_one({"_id": bson.ObjectId(user_id)})
    if not user:
        user = await db.users.find_one({"email": email})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return UserResponse(
        id=str(user["_id"]),
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        class_id=str(user["class_id"]) if user.get("class_id") else None,
        roll_no=user.get("roll_no"),
        is_active=user.get("is_active", True),
        created_at=user["created_at"],
    )


async def get_current_user_optional(
    request: Request,
) -> UserResponse | None:
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

        user = await db.users.find_one({"_id": bson.ObjectId(user_id)})
        if not user:
            user = await db.users.find_one({"email": email})

        if not user or not user.get("is_active", True):
            return None

        return UserResponse(
            id=str(user["_id"]),
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            class_id=str(user["class_id"]) if user.get("class_id") else None,
            roll_no=user.get("roll_no"),
            is_active=user.get("is_active", True),
            created_at=user["created_at"],
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
