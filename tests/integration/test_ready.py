"""Integration tests for /ready against a real PostgreSQL server."""

import pytest

from lexbh.config import Settings
from lexbh.main import create_app
from tests.conftest import running_client

pytestmark = pytest.mark.integration


async def test_ready_returns_200_when_database_is_reachable() -> None:
    app = create_app(Settings())

    async with running_client(app) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
