FROM python:3.12-slim AS build

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir .


# Development tools. The repository is bind mounted over /workspace at run time.
FROM python:3.12-slim AS dev

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MYPY_CACHE_DIR=/tmp/mypy \
    RUFF_CACHE_DIR=/tmp/ruff \
    PYTEST_ADDOPTS="-o cache_dir=/tmp/pytest"

WORKDIR /workspace
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -e ".[dev]"


# Keep this stage last so a plain docker build produces the production image.
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system --gid 10001 lexbh \
    && useradd --system --uid 10001 --gid lexbh --no-create-home --shell /usr/sbin/nologin lexbh

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY alembic.ini ./
COPY migrations ./migrations

USER lexbh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

CMD ["uvicorn", "lexbh.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
