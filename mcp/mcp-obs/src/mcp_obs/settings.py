"""Runtime settings for observability MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    victorialogs_url: str
    victoriatraces_url: str


def _resolve_url(name: str, fallback: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value.rstrip("/")
    return fallback


def resolve_settings() -> Settings:
    return Settings(
        victorialogs_url=_resolve_url("NANOBOT_VICTORIALOGS_URL", "http://localhost:9428"),
        victoriatraces_url=_resolve_url("NANOBOT_VICTORIATRACES_URL", "http://localhost:10428"),
    )
