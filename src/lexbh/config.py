"""Typed application settings loaded from the environment and an optional .env file."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

REQUIRED_DATABASE_DRIVER = "postgresql+asyncpg"


class Settings(BaseSettings):
    """Runtime configuration. Every field maps to a ``LEXBH_``-prefixed variable."""

    model_config = SettingsConfigDict(
        env_prefix="LEXBH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    database_url: SecretStr
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    readiness_timeout_seconds: float = Field(default=2.0, gt=0)

    @field_validator("database_url")
    @classmethod
    def require_asyncpg_driver(cls, value: SecretStr) -> SecretStr:
        """Reject URLs for any driver other than asyncpg, without echoing the URL."""
        try:
            driver = make_url(value.get_secret_value()).drivername
        except ArgumentError:
            raise ValueError("database_url is not a valid database URL") from None
        if driver != REQUIRED_DATABASE_DRIVER:
            raise ValueError(f"database_url must use the {REQUIRED_DATABASE_DRIVER} driver")
        return value

    @property
    def json_logs(self) -> bool:
        """Emit JSON logs everywhere except local development."""
        return self.environment != "local"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
