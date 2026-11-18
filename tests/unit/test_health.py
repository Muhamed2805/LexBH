"""Unit tests for /health and /ready. None of these need a running database."""

import socket
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import event

from lexbh.config import Settings
from lexbh.db import Database
from lexbh.main import create_app
from tests.conftest import running_client

FICTIONAL_USER = "fictional_user"
FICTIONAL_PASSWORD = "fictional_secret"


@pytest.fixture
def unreachable_settings() -> Settings:
    """Settings pointing at a local port that nothing is listening on."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return Settings(
        _env_file=None,
        environment="test",
        database_url=SecretStr(
            f"postgresql+asyncpg://{FICTIONAL_USER}:{FICTIONAL_PASSWORD}"
            f"@127.0.0.1:{port}/fictional_db"
        ),
        readiness_timeout_seconds=0.5,
    )


async def test_health_returns_ok_without_touching_the_database(
    unreachable_settings: Settings,
) -> None:
    app = create_app(unreachable_settings)
    connection_attempts: list[Any] = []

    async with running_client(app) as client:
        database: Database = app.state.database
        event.listen(
            database.engine.sync_engine,
            "do_connect",
            lambda *args: connection_attempts.append(args),
        )
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert connection_attempts == []


async def test_ready_returns_503_when_database_is_unavailable(
    unreachable_settings: Settings,
) -> None:
    app = create_app(unreachable_settings)

    async with running_client(app) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


async def test_ready_failure_does_not_leak_connection_details(
    unreachable_settings: Settings,
) -> None:
    app = create_app(unreachable_settings)

    async with running_client(app) as client:
        response = await client.get("/ready")

    for secret in (FICTIONAL_USER, FICTIONAL_PASSWORD, "127.0.0.1", "fictional_db", "asyncpg"):
        assert secret not in response.text


async def test_app_starts_while_database_is_unavailable(unreachable_settings: Settings) -> None:
    app = create_app(unreachable_settings)

    async with running_client(app) as client:
        assert (await client.get("/health")).status_code == 200
