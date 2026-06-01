# syntax=docker/dockerfile:1
FROM python:3.12-slim

# uv (pinned binary from the official image)
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first for layer caching (no project, no dev deps).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the source + install the project.
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000
# Default command runs the API; the worker overrides this in docker-compose.
CMD ["uvicorn", "triage.main:app", "--host", "0.0.0.0", "--port", "8000"]
