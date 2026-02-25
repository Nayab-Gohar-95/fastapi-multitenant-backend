"""
api/routes/admin.py
-------------------
Admin-only endpoints for user management within a tenant.

POST /admin/users  — Admin creates a new user (any role) in their tenant.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: create a new user in the current tenant",
)
async def admin_create_user(
    body: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> UserRead:
    """
    Allows an admin to create users (including other admins) within
    their own tenant. The tenant_id is sourced from the admin's JWT —
    admins cannot create users in other tenants.
    """
    try:
        user = await UserService.create_user_by_admin(
            db=db,
            data=body,
            tenant_id=admin.tenant_id,
        )
        return UserRead.model_validate(user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
