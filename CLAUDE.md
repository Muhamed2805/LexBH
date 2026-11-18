# LexBH

Open-source agentic RAG system that answers questions about the laws of Bosnia and Herzegovina and
cites the exact article.

## Standing rules

- Never commit or push. The maintainer handles all git work by hand.
- Never add real legal texts to the repository unless the maintainer confirms the source allows it.
- Test fixtures must be synthetic and clearly marked as fictional.
- Every answer the system generates must be backed by a cited source.

## Stack

- Python 3.12, src layout (`src/lexbh`), `pyproject.toml` with hatchling
- Plain venv and pip, with dev dependencies in the `dev` extra
- FastAPI and Uvicorn
- pydantic-settings, using `LEXBH_`-prefixed variables
- PostgreSQL 17 with pgvector (`pgvector/pgvector:pg17`), published on `127.0.0.1:5433`
- SQLAlchemy 2.x async with asyncpg (`postgresql+asyncpg://`). Do not use psycopg async, because it
  does not work with the default Windows event loop
- Alembic with an async `migrations/env.py`. Migrations run only through an explicit command, never
  on application startup
- pytest, pytest-asyncio, httpx, ruff, and mypy in strict mode

## Commands (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

ruff check .
ruff format --check .
mypy src tests
pytest

docker compose up -d db
alembic upgrade head
pytest -m integration

uvicorn lexbh.main:create_app --factory --reload
docker compose down
```

Plain `pytest` runs unit tests only. `pytest -m integration` needs the database running.
