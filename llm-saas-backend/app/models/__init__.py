"""
models/__init__.py
------------------
Re-export all models so Alembic's env.py can import Base and discover
all tables via a single import:

    from app.models import Base
"""

from app.db.base import Base
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.message import Message

__all__ = ["Base", "Tenant", "User", "UserRole", "Message"]
