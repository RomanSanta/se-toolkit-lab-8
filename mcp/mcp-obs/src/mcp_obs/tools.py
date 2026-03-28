"""Tool schemas and handlers for observability MCP server."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from mcp.types import Tool
from pydantic import BaseModel

from mcp_obs.observability import (
    ErrorCountArgs,
    ErrorCountRow,
    LogEntry,
    LogSearchArgs,
    ObservabilityClient,
    TraceDetails,
    TraceGetArgs,
    TracesListArgs,
    TraceSummary,
)


ToolPayload = BaseModel | Sequence[BaseModel]
ToolHandler = Callable[[ObservabilityClient, BaseModel], Awaitable[ToolPayload]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    model: type[BaseModel]
    handler: ToolHandler

    def as_tool(self) -> Tool:
        schema = self.model.model_json_schema()
        schema.pop("$defs", None)
        schema.pop("title", None)
        return Tool(name=self.name, description=self.description, inputSchema=schema)


async def _logs_search(client: ObservabilityClient, args: BaseModel) -> list[LogEntry]:
    return await client.logs_search(_require(args, LogSearchArgs))


async def _logs_error_count(
    client: ObservabilityClient, args: BaseModel
) -> list[ErrorCountRow]:
    return await client.logs_error_count(_require(args, ErrorCountArgs))


async def _traces_list(
    client: ObservabilityClient, args: BaseModel
) -> list[TraceSummary]:
    return await client.traces_list(_require(args, TracesListArgs))


async def _traces_get(client: ObservabilityClient, args: BaseModel) -> TraceDetails:
    return await client.traces_get(_require(args, TraceGetArgs))


def _require[TModel: BaseModel](args: BaseModel, model: type[TModel]) -> TModel:
    if not isinstance(args, model):
        raise TypeError(f"Expected {model.__name__}, got {type(args).__name__}")
    return args


TOOL_SPECS = (
    ToolSpec(
        "logs_search",
        "Search VictoriaLogs entries by time range and optional service/severity/keyword filters.",
        LogSearchArgs,
        _logs_search,
    ),
    ToolSpec(
        "logs_error_count",
        "Count ERROR log events per service over a time window.",
        ErrorCountArgs,
        _logs_error_count,
    ),
    ToolSpec(
        "traces_list",
        "List recent traces for a service from VictoriaTraces.",
        TracesListArgs,
        _traces_list,
    ),
    ToolSpec(
        "traces_get",
        "Fetch one trace by trace_id and return simplified span data.",
        TraceGetArgs,
        _traces_get,
    ),
)
TOOLS_BY_NAME = {spec.name: spec for spec in TOOL_SPECS}
