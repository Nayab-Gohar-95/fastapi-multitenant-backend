"""
api/routes/auth.py
------------------
Authentication endpoints.

POST /register  — Self-registration into an existing tenant.
POST /login     — Exchange credentials for a JWT access token.
                  Accepts BOTH OAuth2 form data (Swagger UI) and JSON body.
GET  /me        — Return the authenticated user's profile.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import (
    TokenResponse,
    UserRead,
    UserRegister,
)
from app.services.tenant_service import TenantService
from app.services.user_service import UserService

router = APIRouter(tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    body: UserRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    """
    Create a new user account inside an existing tenant.
    The tenant_id must correspond to an existing tenant.
    Default role is 'user'.
    """
    tenant = await TenantService.get_tenant_by_id(db, body.tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{body.tenant_id}' not found",
        )
    try:
        user = await UserService.register_user(db, body)
        return UserRead.model_validate(user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive a JWT access token",
)
async def login(
    # OAuth2PasswordRequestForm sends username + password as form data.
    # Swagger's Authorize popup uses this format automatically.
    # The "username" field contains the email address.
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    Authenticate with email + password and receive a signed JWT.

    In Swagger UI: use the Authorize button and enter your email as username.
    Via curl/Postman: send as form data (not JSON):
        -d "username=you@email.com&password=yourpassword"
    """
    # form_data.username holds the email (OAuth2 spec uses "username")
    user = await UserService.authenticate(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        subject=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        expires_delta=expires,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=int(expires.total_seconds()),
        user=UserRead.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the currently authenticated user",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return UserRead.model_validate(current_user)