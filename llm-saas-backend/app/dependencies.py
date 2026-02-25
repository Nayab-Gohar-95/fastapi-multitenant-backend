"""
dependencies.py
---------------
FastAPI dependency injection functions for authentication and authorisation.

Flow:
  1. OAuth2PasswordBearer extracts the Bearer token from the Authorization header.
  2. decode_access_token validates and parses the JWT (no DB round-trip).
  3. get_current_user fetches the full User record from the DB, verifying the
     token's sub (user_id) and tenant_id against persisted data.
  4. get_current_admin layers a role check on top of get_current_user.

The tenant_id embedded in the JWT is used to scope every DB query, preventing
cross-tenant data access even if a user's role is elevated.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

logger = get_logger(__name__)

# tokenUrl must match the login endpoint path
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Decode the JWT, then load and return the full User from the database.
    Raises 401 if the token is invalid or the user no longer exists.
    """
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")
        if not user_id or not tenant_id:
            raise _CREDENTIALS_EXCEPTION
    except JWTError as exc:
        logger.warning("JWT decode failed", error=str(exc))
        raise _CREDENTIALS_EXCEPTION

    # Always re-verify against DB so revoked / deleted users are rejected
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("User from valid JWT not found in DB", user_id=user_id)
        raise _CREDENTIALS_EXCEPTION

    return user


async def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Extends get_current_user with an admin role check.
    Raises 403 if the authenticated user is not an admin.
    """
    if current_user.role != UserRole.admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
