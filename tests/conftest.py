"""Shared test helpers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Yield an HTTP client for ``app`` with its lifespan running."""
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as client,
    ):
        yield client
