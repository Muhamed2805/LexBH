# LexBH

Open-source agentic RAG system that answers questions about the laws of Bosnia and Herzegovina and
cites the exact article.

## Standing rules

- Never commit or push. The maintainer handles all git work by hand.
- Never add real legal texts to the repository unless the maintainer confirms the source allows it.
- Test fixtures must be synthetic and clearly marked as fictional.
- Every answer the system generates must be backed by a cited source.
- Never disable, change, or work around Windows Smart App Control. It may block native Windows
  tools, so run project checks in the `dev` container.
- Never run `docker compose down -v`. The database volume must be kept.

## Stack

- Python 3.12, src layout (`src/lexbh`), `pyproject.toml` with hatchling
- Venv and pip inside the `dev` container, with dev dependencies in the `dev` extra
- FastAPI and Uvicorn
- pydantic-settings, using `LEXBH_`-prefixed variables
- PostgreSQL 17 with pgvector (`pgvector/pgvector:pg17`), published on `127.0.0.1:5433`
- SQLAlchemy 2.x async with asyncpg (`postgresql+asyncpg://`). Do not use psycopg async, because it
  does not work with the default Windows event loop
- Alembic with an async `migrations/env.py`. Migrations run only through an explicit command, never
  on application startup
- pytest, pytest-asyncio, httpx, ruff, and mypy in strict mode

## Commands (Windows PowerShell)

Checks run in the `dev` container, with the repository bind mounted at `/workspace`:

```powershell
Copy-Item .env.example .env
docker compose --profile dev build dev

docker compose run --rm dev ruff check .
docker compose run --rm dev ruff format --check .
docker compose run --rm dev mypy src tests
docker compose run --rm dev pytest
docker compose run --rm dev pytest -m integration
```

Plain `pytest` runs unit tests only. `pytest -m integration` uses the `db` service.

Run the API:

```powershell
docker compose build api
docker compose up -d db
docker compose run --rm api alembic upgrade head
docker compose run --rm api alembic current
docker compose up -d api
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
docker compose down
```
