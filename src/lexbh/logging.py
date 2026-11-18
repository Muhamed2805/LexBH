"""Structured logging: JSON outside local development, readable text locally."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from lexbh.config import Settings

_RESERVED_RECORD_FIELDS = frozenset(
    vars(logging.LogRecord("", logging.INFO, "", 0, "", None, None)).keys()
    | {"message", "asctime", "taskName", "color_message"}
)
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")
_TEXT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


class JsonFormatter(logging.Formatter):
    """Render each log record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            (key, value)
            for key, value in vars(record).items()
            if key not in _RESERVED_RECORD_FIELDS
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    """Install one stdout handler on the root logger and route Uvicorn through it."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter() if settings.json_logs else logging.Formatter(_TEXT_FORMAT)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.log_level)

    for name in _UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
