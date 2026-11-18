"""Unit tests for application settings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from lexbh.config import Settings

VALID_URL = "postgresql+asyncpg://fictional_user:fictional_secret@127.0.0.1:5433/fictional_db"
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's shell from influencing these tests."""
    for field in Settings.model_fields:
        monkeypatch.delenv(f"LEXBH_{field.upper()}", raising=False)


def test_loads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEXBH_DATABASE_URL", VALID_URL)
    monkeypatch.setenv("LEXBH_ENVIRONMENT", "production")
    monkeypatch.setenv("LEXBH_DATABASE_POOL_SIZE", "12")

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.database_pool_size == 12
    assert settings.database_url.get_secret_value() == VALID_URL


def test_loads_values_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"LEXBH_DATABASE_URL={VALID_URL}\nLEXBH_LOG_LEVEL=DEBUG\nPOSTGRES_USER=ignored\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.log_level == "DEBUG"


def test_environment_overrides_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"LEXBH_DATABASE_URL={VALID_URL}\nLEXBH_LOG_LEVEL=DEBUG\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LEXBH_LOG_LEVEL", "ERROR")

    assert Settings(_env_file=env_file).log_level == "ERROR"


def test_database_url_is_required() -> None:
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://fictional_user:fictional_secret@127.0.0.1:5433/fictional_db",
        "postgresql://fictional_user:fictional_secret@127.0.0.1:5433/fictional_db",
        "not a url fictional_secret",
    ],
)
def test_rejects_other_drivers_without_leaking_the_url(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("LEXBH_DATABASE_URL", url)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert "fictional_secret" not in str(error.value)


def test_database_url_is_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEXBH_DATABASE_URL", VALID_URL)

    assert "fictional_secret" not in repr(Settings(_env_file=None))


@pytest.mark.parametrize(
    ("environment", "expected"),
    [("local", False), ("test", True), ("staging", True), ("production", True)],
)
def test_json_logs_outside_local_development(
    monkeypatch: pytest.MonkeyPatch, environment: str, expected: bool
) -> None:
    monkeypatch.setenv("LEXBH_DATABASE_URL", VALID_URL)
    monkeypatch.setenv("LEXBH_ENVIRONMENT", environment)

    assert Settings(_env_file=None).json_logs is expected


def test_env_example_documents_every_setting() -> None:
    lines = (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    documented = {line.split("=", 1)[0] for line in lines if line.startswith("LEXBH_")}

    assert documented == {f"LEXBH_{field.upper()}" for field in Settings.model_fields}
