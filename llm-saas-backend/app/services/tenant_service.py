"""
services/tenant_service.py
--------------------------
Business logic for tenant management.

Service layer is responsible for:
  - Constructing queries
  - Enforcing business rules (e.g. unique names)
  - Returning domain objects (ORM models) to the route layer
  - Never returning HTTP responses (that's the route's job)
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate

logger = get_logger(__name__)


class TenantService:

    @staticmethod
    async def create_tenant(db: AsyncSession, data: TenantCreate) -> Tenant:
        """
        Create a new tenant.
        Raises ValueError if a tenant with the same name already exists.
        """
        tenant = Tenant(name=data.name)
        db.add(tenant)
        try:
            await db.flush()  # Trigger DB constraints before commit
            await db.refresh(tenant)
            logger.info("Tenant created", tenant_id=tenant.id, name=tenant.name)
            return tenant
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Tenant '{data.name}' already exists")

    @staticmethod
    async def get_tenant_by_id(db: AsyncSession, tenant_id: str) -> Tenant | None:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_tenant_by_name(db: AsyncSession, name: str) -> Tenant | None:
        result = await db.execute(select(Tenant).where(Tenant.name == name))
        return result.scalar_one_or_none()
