"""
db/base.py
----------
Declarative base and shared mixins.

TimestampMixin:  Adds created_at / updated_at columns to any model.
UUIDPrimaryKey: Uses PostgreSQL's native UUID type as primary key.
                UUIDs are preferable over integer sequences in multi-tenant
                systems because they prevent tenant enumeration attacks.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class TimestampMixin:
    """Adds server-side created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def generate_uuid() -> str:
    return str(uuid.uuid4())
