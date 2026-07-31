# Image for the runnable example project only — the package itself needs no Docker.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# The test group carries the demo's runtime extras: uvicorn, gunicorn, structlog.
RUN uv sync --frozen --no-default-groups --group test

COPY manage.py ./
COPY example ./example

CMD ["python", "-m", "uvicorn", "example.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
