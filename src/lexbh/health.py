"""Liveness and readiness endpoints."""

from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from lexbh.config import Settings
from lexbh.db import Database

router = APIRouter(tags=["operations"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ready", "unavailable"]


@router.get("/health")
async def health() -> HealthResponse:
    """Report that the process is alive. Never touches the database."""
    return HealthResponse()


@router.get(
    "/ready",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def ready(request: Request, response: Response) -> ReadinessResponse:
    """Report whether the database answers ``SELECT 1``."""
    database: Database = request.app.state.database
    settings: Settings = request.app.state.settings
    if await database.is_reachable(settings.readiness_timeout_seconds):
        return ReadinessResponse(status="ready")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="unavailable")
