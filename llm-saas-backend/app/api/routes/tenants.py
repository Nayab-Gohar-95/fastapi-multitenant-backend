"""
api/routes/tenants.py
---------------------
Tenant management endpoints.

POST /create-tenant  — Public endpoint to onboard a new company/tenant.
GET  /tenants/{tenant_id}/users — Admin-only: list users in a tenant.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantRead
from app.schemas.user import UserRead
from app.services.tenant_service import TenantService
from app.services.user_service import UserService

router = APIRouter(tags=["Tenants"])


@router.post(
    "/create-tenant",
    response_model=TenantRead,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard a new tenant (company)",
)
async def create_tenant(
    body: TenantCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantRead:
    """
    Public endpoint — no authentication required.
    In production you may want to restrict this to an internal
    admin portal or require an invite token.
    """
    try:
        tenant = await TenantService.create_tenant(db, body)
        return TenantRead.model_validate(tenant)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get(
    "/tenants/{tenant_id}/users",
    response_model=list[UserRead],
    summary="List all users in a tenant (admin only)",
)
async def list_tenant_users(
    tenant_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> list[UserRead]:
    """
    Admin-only.
    An admin can only list users within their own tenant — they cannot
    query other tenants even if they know the tenant_id.
    """
    if admin.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view users within your own tenant",
        )
    users = await UserService.list_users_in_tenant(db, tenant_id)
    return [UserRead.model_validate(u) for u in users]
