"""Fixtures for tests that need a real PostgreSQL server with pgvector."""

import asyncio
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from lexbh.config import Settings


@pytest.fixture
def server_url() -> URL:
    """URL of the configured server, from the environment or .env."""
    return make_url(Settings().database_url.get_secret_value())


async def _execute_autocommit(url: URL, statement: str) -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()


@pytest.fixture
def temporary_database_url(server_url: URL) -> Iterator[str]:
    """Create a throwaway database so migration tests never touch development data."""
    name = f"lexbh_test_{uuid4().hex}"
    asyncio.run(_execute_autocommit(server_url, f'CREATE DATABASE "{name}"'))
    try:
        yield server_url.set(database=name).render_as_string(hide_password=False)
    finally:
        asyncio.run(_execute_autocommit(server_url, f'DROP DATABASE "{name}" WITH (FORCE)'))
