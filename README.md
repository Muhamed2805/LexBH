# LexBH

LexBH is an open-source agentic RAG system that answers questions about the laws of Bosnia and
Herzegovina and cites the exact article behind each answer.

> **LexBH does not give legal advice.** Its output is general information only and may be
> incomplete, outdated, or wrong. Always check the official text of the law, and consult a
> qualified lawyer about your situation.

This repository currently contains the project foundation: the API service, database, migrations,
tests, and CI. Question answering is not built yet.

## Requirements

- Docker Desktop

All project tools run in Linux containers.

> **Windows note:** Smart App Control may block native Windows builds of tools such as `pytest`,
> `alembic`, and `uvicorn`, and compiled Python packages such as SQLAlchemy. Keep Smart App Control
> enabled and use the container commands below.

## Setup (Windows PowerShell)

Create your local configuration:

```powershell
Copy-Item .env.example .env
```

Build the development image:

```powershell
docker compose --profile dev build dev
```

## Checks

```powershell
docker compose run --rm dev ruff check .
docker compose run --rm dev ruff format --check .
docker compose run --rm dev mypy src tests
docker compose run --rm dev pytest
docker compose run --rm dev pytest -m integration
```

Plain `pytest` runs unit tests only. Integration tests use the `db` service, which starts
automatically.

## Inspecting a local law file

The inspection tool shows how the parser reads a law text file. It only reads its input.

Real law texts stay in `data/raw/`, which is gitignored. They must never be committed.

```powershell
docker compose run --rm --no-deps dev python -m lexbh.ingestion.cli data/raw/<file>.txt --law-id <slug> --title "<title>" --jurisdiction BIH
```

Add `--articles` for a document outline. Files are read as UTF-8 by default, so use
`--encoding cp1250` for older Windows files.

| Exit code | Meaning                                                                 |
| --------- | ----------------------------------------------------------------------- |
| `0`       | No error-severity diagnostics and no unassigned text                    |
| `1`       | At least one error-severity diagnostic, or unassigned text              |
| `2`       | Usage error, unreadable file, damaged text, bad metadata, or no article |

## Running the API

Build the API image and start PostgreSQL, which is published on `127.0.0.1:5433`:

```powershell
docker compose build api
docker compose up -d db
```

Apply the migrations. They never run automatically on application startup:

```powershell
docker compose run --rm api alembic upgrade head
docker compose run --rm api alembic current
```

Start the API and check it:

```powershell
docker compose up -d api
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

| Endpoint      | Purpose   | Response                                       |
| ------------- | --------- | ---------------------------------------------- |
| `GET /health` | Liveness  | `200` without touching the database            |
| `GET /ready`  | Readiness | `200` if the database answers, otherwise `503` |

Stop everything and keep the database volume:

```powershell
docker compose down
```
