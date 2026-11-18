"""Integration tests for the Alembic migrations, run in a throwaway database."""

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]


def alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


async def _scalar(database_url: str, statement: str) -> object:
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return (await connection.execute(text(statement))).scalar_one_or_none()
    finally:
        await engine.dispose()


def vector_extension_exists(database_url: str) -> bool:
    statement = "SELECT count(*) FROM pg_extension WHERE extname = 'vector'"
    return asyncio.run(_scalar(database_url, statement)) == 1


def current_revision(database_url: str) -> object:
    return asyncio.run(_scalar(database_url, "SELECT version_num FROM alembic_version"))


def test_upgrade_creates_vector_extension(temporary_database_url: str) -> None:
    config = alembic_config(temporary_database_url)
    assert not vector_extension_exists(temporary_database_url)

    command.upgrade(config, "head")

    assert vector_extension_exists(temporary_database_url)
    assert current_revision(temporary_database_url) == (
        ScriptDirectory.from_config(config).get_current_head()
    )


def test_vector_type_is_usable_after_upgrade(temporary_database_url: str) -> None:
    command.upgrade(alembic_config(temporary_database_url), "head")

    distance = asyncio.run(
        _scalar(temporary_database_url, "SELECT '[1,2,3]'::vector <-> '[1,2,3]'::vector")
    )

    assert distance == 0


def test_downgrade_removes_vector_extension(temporary_database_url: str) -> None:
    config = alembic_config(temporary_database_url)
    command.upgrade(config, "head")

    command.downgrade(config, "base")

    assert not vector_extension_exists(temporary_database_url)
    assert current_revision(temporary_database_url) is None


def test_upgrade_works_again_after_downgrade(temporary_database_url: str) -> None:
    config = alembic_config(temporary_database_url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    command.upgrade(config, "head")

    assert vector_extension_exists(temporary_database_url)
