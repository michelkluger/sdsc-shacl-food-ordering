# syntax=docker/dockerfile:1
#
# Build context is the repository root, so the image can be built the same way from CI and from
# compose. Two stages: uv resolves and installs into a virtualenv, the runtime stage copies it.
# The runtime image has no uv, no compiler and no build metadata.

FROM ghcr.io/astral-sh/uv:0.8.3-python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, in their own layer: they change far less often than the source, so an
# edit to a .py file does not re-resolve the whole environment.
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY backend/src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.13-slim-bookworm AS runtime

# No curl: the compose healthcheck probes /api/healthz with the interpreter that is already in
# the image (`python -c urllib...`), so installing an HTTP client to do the same job would be
# one more package in the runtime layer for nothing.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FOOD_API_MEILI_URL=http://meilisearch:7700

USER appuser
EXPOSE 8000

# Fails fast and loudly if a shape does not parse, rather than serving a half-loaded catalogue.
CMD ["uvicorn", "food_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
