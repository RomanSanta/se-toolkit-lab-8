ARG REGISTRY_PREFIX_DOCKER_HUB
FROM ${REGISTRY_PREFIX_DOCKER_HUB}astral/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

COPY --from=workspace pyproject.toml uv.lock /app/
COPY --from=workspace nanobot/pyproject.toml /app/nanobot/pyproject.toml
COPY --from=workspace mcp/mcp-lms/pyproject.toml /app/mcp/mcp-lms/pyproject.toml
COPY --from=workspace mcp/mcp-obs/pyproject.toml /app/mcp/mcp-obs/pyproject.toml
COPY --from=workspace nanobot-websocket-channel/nanobot-channel-protocol/pyproject.toml /app/nanobot-websocket-channel/nanobot-channel-protocol/pyproject.toml
COPY --from=workspace nanobot-websocket-channel/mcp-webchat/pyproject.toml /app/nanobot-websocket-channel/mcp-webchat/pyproject.toml
COPY --from=workspace nanobot-websocket-channel/nanobot-webchat/pyproject.toml /app/nanobot-websocket-channel/nanobot-webchat/pyproject.toml

COPY --from=workspace nanobot /app/nanobot
COPY --from=workspace mcp /app/mcp
COPY --from=workspace nanobot-websocket-channel /app/nanobot-websocket-channel

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package nanobot

ARG REGISTRY_PREFIX_DOCKER_HUB
FROM ${REGISTRY_PREFIX_DOCKER_HUB}python:3.14.2-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8

ARG APP_UID=1000
ARG APP_GID=1000

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app/nanobot
USER ${APP_UID}:${APP_GID}

CMD ["python", "/app/nanobot/entrypoint.py"]
