"""Async database engine and session factory."""

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from lexbh.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Database:
    """Owns the engine and session factory for one application lifespan."""

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    async def is_reachable(self, timeout_seconds: float) -> bool:
        """Run ``SELECT 1`` and report whether it succeeded within the timeout.

        Any failure means the database is not ready. Only the exception type is logged,
        because driver messages can contain hosts, ports, and user names.
        """
        try:
            async with asyncio.timeout(timeout_seconds), self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:
            logger.warning("database readiness check failed", extra={"error": type(exc).__name__})
            return False
        return True

    async def dispose(self) -> None:
        """Close every pooled connection."""
        await self.engine.dispose()


def create_database(settings: Settings) -> Database:
    """Build the engine and session factory. No connection is opened here."""
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
    )
    return Database(
        engine=engine,
        session_factory=async_sessionmaker(engine, expire_on_commit=False),
    )
