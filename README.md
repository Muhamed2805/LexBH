# LexBH

LexBH is an open-source agentic RAG system that answers questions about the laws of Bosnia and
Herzegovina and cites the exact article behind each answer.

> **LexBH does not give legal advice.** Its output is general information only and may be
> incomplete, outdated, or wrong. Always check the official text of the law, and consult a
> qualified lawyer about your situation.

This repository currently contains the project foundation: the API service, database, migrations,
tests, and CI. Question answering is not built yet.

## Requirements

- Python 3.12
- Docker Desktop

## Setup (Windows PowerShell)

Create the virtual environment and install the project:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Create your local configuration:

```powershell
Copy-Item .env.example .env
```

Start PostgreSQL, which is published on `127.0.0.1:5433`:

```powershell
docker compose up -d db
```

Apply the migrations. They never run automatically on application startup:

```powershell
alembic upgrade head
```

Start the API:

```powershell
uvicorn lexbh.main:create_app --factory --reload
```

Check it from a second terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

| Endpoint      | Purpose   | Response                                            |
| ------------- | --------- | --------------------------------------------------- |
| `GET /health` | Liveness  | `200` without touching the database                 |
| `GET /ready`  | Readiness | `200` if the database answers, otherwise `503`      |

Stop the database and keep its data:

```powershell
docker compose down
```

## Running the API in Docker

```powershell
docker compose up -d --build
docker compose run --rm api alembic upgrade head
```

## Checks

```powershell
ruff check .
ruff format --check .
mypy src tests
pytest
```

Integration tests need the database from `docker compose up -d db`:

```powershell
pytest -m integration
```
