"""FastAPI application factory.

Run with ``uvicorn lexbh.main:create_app --factory``. Migrations are never run from here.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lexbh.config import Settings, get_settings
from lexbh.db import create_database
from lexbh.health import router as health_router
from lexbh.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the database resources once and dispose of them on shutdown."""
    database = create_database(app.state.settings)
    app.state.database = database
    try:
        yield
    finally:
        await database.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured application instance."""
    resolved_settings = settings if settings is not None else get_settings()
    configure_logging(resolved_settings)

    app = FastAPI(title="LexBH", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.include_router(health_router)
    return app
