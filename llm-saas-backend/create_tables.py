"""
create_tables.py
----------------
One-shot script to create all database tables.
Use this for quick setup. For production migrations, use Alembic instead.

Usage:
    python create_tables.py
"""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.models import Base  # Imports all models so metadata is populated


async def create_all_tables() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("✅  All tables created successfully.")


if __name__ == "__main__":
    asyncio.run(create_all_tables())
