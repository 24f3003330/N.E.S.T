"""
N.E.S.T – Async SQLAlchemy engine, session, and declarative base.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ── Engine ──
engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}

# If using PostgreSQL (Render/Supabase), disable prepared statement caching
# because PgBouncer (transaction mode) does not support it properly.
if "postgresql" in settings.DATABASE_URL:
    engine_kwargs["connect_args"] = {"statement_cache_size": 0}

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

# ── Session factory ──
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative base ──
class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ── Dependency for FastAPI routes ──
async def get_db() -> AsyncSession:  # type: ignore[misc]
    """Yield an async database session, auto-closed on exit."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
