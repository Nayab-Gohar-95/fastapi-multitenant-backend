"""
db/session.py
-------------
Async SQLAlchemy engine and session factory.

Design decisions:
  - AsyncEngine with asyncpg driver for non-blocking I/O.
  - Connection pool sized for typical SaaS workloads:
      pool_size=10, max_overflow=20 → max 30 concurrent DB connections.
  - pool_pre_ping=True: validates connections before checkout to handle
    stale connections after DB restarts or idle timeouts.
  - expire_on_commit=False: avoids lazy-load errors after commit in async
    context (attributes are already loaded, no implicit SELECT needed).
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,          # Log SQL in development
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,             # Recycle connections every hour
)

# ── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:  # type: ignore[return]
    """
    FastAPI dependency that yields a database session.
    The session is automatically closed when the request finishes,
    and rolled back on exceptions.

    Usage:
        @router.get("/example")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
