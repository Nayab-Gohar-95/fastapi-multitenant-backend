"""
services/user_service.py
------------------------
Business logic for user registration, authentication, and listing.

All queries are scoped by tenant_id to enforce strict data isolation.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserRegister

logger = get_logger(__name__)


class UserService:

    @staticmethod
    async def register_user(db: AsyncSession, data: UserRegister) -> User:
        """
        Self-registration: creates a 'user'-role account in the specified tenant.
        Raises ValueError on duplicate email.
        """
        user = User(
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            role=UserRole.user.value,
            tenant_id=data.tenant_id,
        )
        db.add(user)
        try:
            await db.flush()
            await db.refresh(user)
            logger.info("User registered", user_id=user.id, tenant_id=user.tenant_id)
            return user
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Email '{data.email}' is already registered")

    @staticmethod
    async def create_user_by_admin(
        db: AsyncSession,
        data: UserCreate,
        tenant_id: str,
    ) -> User:
        """
        Admin-initiated user creation within their own tenant.
        Admins can assign any role.
        """
        user = User(
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            role=data.role.value,
            tenant_id=tenant_id,
        )
        db.add(user)
        try:
            await db.flush()
            await db.refresh(user)
            logger.info(
                "Admin created user",
                new_user_id=user.id,
                role=user.role,
                tenant_id=tenant_id,
            )
            return user
        except IntegrityError:
            await db.rollback()
            raise ValueError(f"Email '{data.email}' is already registered")

    @staticmethod
    async def authenticate(
        db: AsyncSession, email: str, password: str
    ) -> User | None:
        """
        Verify credentials and return the User if valid, else None.
        Email lookup is case-insensitive.
        """
        result = await db.execute(
            select(User).where(User.email == email.lower())
        )
        user = result.scalar_one_or_none()
        if user is None or not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    async def list_users_in_tenant(
        db: AsyncSession, tenant_id: str
    ) -> list[User]:
        """
        Return all users belonging to a given tenant.
        Used by admin-only endpoints.
        """
        result = await db.execute(
            select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)
        )
        return list(result.scalars().all())
