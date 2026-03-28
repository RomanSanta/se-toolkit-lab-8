"""Async clients and data models for VictoriaLogs and VictoriaTraces."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import httpx
from pydantic import BaseModel, Field


class LogSearchArgs(BaseModel):
    minutes: int = Field(default=10, ge=1, le=24 * 60)
    limit: int = Field(default=20, ge=1, le=200)
    service: str | None = Field(default=None)
    severity: str | None = Field(default=None, description="INFO/WARN/ERROR...")
    keyword: str | None = Field(default=None, description="Optional full-text keyword")


class ErrorCountArgs(BaseModel):
    minutes: int = Field(default=60, ge=1, le=24 * 60)
    service: str | None = Field(default=None)
    limit: int = Field(default=10, ge=1, le=1000)


class TracesListArgs(BaseModel):
    service: str = Field(description="Service name, e.g. Learning Management Service")
    limit: int = Field(default=5, ge=1, le=50)


class TraceGetArgs(BaseModel):
    trace_id: str = Field(description="Trace id from logs trace_id field")


class LogEntry(BaseModel):
    time: str
    severity: str | None = None
    service: str | None = None
    event: str | None = None
    message: str | None = None
    trace_id: str | None = None
    path: str | None = None
    status: str | None = None
    error: str | None = None


class ErrorCountRow(BaseModel):
    service: str
    errors: int


class TraceSummary(BaseModel):
    trace_id: str
    root_operation: str | None = None
    span_count: int
    start_time_us: int | None = None
    duration_us: int | None = None
    services: list[str]


class TraceSpan(BaseModel):
    span_id: str
    parent_span_id: str | None = None
    operation: str
    service: str | None = None
    duration_ms: float
    status_code: str | None = None
    error: str | None = None


class TraceDetails(BaseModel):
    trace_id: str
    span_count: int
    spans: list[TraceSpan]


class ObservabilityClient:
    def __init__(
        self,
        victorialogs_url: str,
        victoriatraces_url: str,
        *,
        timeout: float = 15.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.victorialogs_url = victorialogs_url.rstrip("/")
        self.victoriatraces_url = victoriatraces_url.rstrip("/")
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> ObservabilityClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()

    async def logs_search(self, args: LogSearchArgs) -> list[LogEntry]:
        query = _build_logsql_query(
            minutes=args.minutes,
            service=args.service,
            severity=args.severity,
            keyword=args.keyword,
        )
        rows = await self._query_logs(query=query, limit=args.limit)
        return [_to_log_entry(row) for row in rows]

    async def logs_error_count(self, args: ErrorCountArgs) -> list[ErrorCountRow]:
        query = _build_logsql_query(
            minutes=args.minutes,
            service=args.service,
            severity="ERROR",
            keyword=None,
        )
        rows = await self._query_logs(query=query, limit=args.limit)
        counts: Counter[str] = Counter()
        for row in rows:
            service = str(row.get("service.name") or row.get("otelServiceName") or "unknown")
            counts[service] += 1
        return [
            ErrorCountRow(service=service, errors=count)
            for service, count in counts.most_common()
        ]

    async def traces_list(self, args: TracesListArgs) -> list[TraceSummary]:
        payload = await self._request_json(
            "GET",
            f"{self.victoriatraces_url}/select/jaeger/api/traces",
            params={"service": args.service, "limit": str(args.limit)},
        )
        traces: list[dict[str, Any]] = payload.get("data", []) if isinstance(payload, dict) else []
        return [_to_trace_summary(trace) for trace in traces]

    async def traces_get(self, args: TraceGetArgs) -> TraceDetails:
        payload = await self._request_json(
            "GET",
            f"{self.victoriatraces_url}/select/jaeger/api/traces/{args.trace_id}",
        )
        traces: list[dict[str, Any]] = payload.get("data", []) if isinstance(payload, dict) else []
        if not traces:
            raise RuntimeError(f"Trace not found: {args.trace_id}")
        trace = traces[0]
        spans = trace.get("spans", []) if isinstance(trace, dict) else []
        processes = trace.get("processes", {}) if isinstance(trace, dict) else {}
        simplified = [_to_trace_span(span, processes) for span in spans if isinstance(span, dict)]
        return TraceDetails(trace_id=args.trace_id, span_count=len(simplified), spans=simplified)

    async def _query_logs(self, *, query: str, limit: int) -> list[dict[str, Any]]:
        response = await self._http_client.get(
            f"{self.victorialogs_url}/select/logsql/query",
            params={"query": query, "limit": str(limit)},
        )
        response.raise_for_status()
        lines = [line.strip() for line in response.text.splitlines() if line.strip()]
        rows: list[dict[str, Any]] = []
        for line in lines:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
    ) -> Any:
        response = await self._http_client.request(method, url, params=params)
        response.raise_for_status()
        return response.json()


def _build_logsql_query(
    *,
    minutes: int,
    service: str | None,
    severity: str | None,
    keyword: str | None,
) -> str:
    parts: list[str] = [f"_time:{minutes}m"]
    if service:
        parts.append(f'service.name:"{service}"')
    if severity:
        parts.append(f"severity:{severity.upper()}")
    if keyword:
        escaped = keyword.replace('"', "")
        parts.append(f'"{escaped}"')
    return " ".join(parts)


def _to_log_entry(row: dict[str, Any]) -> LogEntry:
    return LogEntry(
        time=str(row.get("_time") or ""),
        severity=_str_or_none(row.get("severity")),
        service=_str_or_none(row.get("service.name") or row.get("otelServiceName")),
        event=_str_or_none(row.get("event")),
        message=_str_or_none(row.get("_msg")),
        trace_id=_str_or_none(row.get("trace_id") or row.get("otelTraceID")),
        path=_str_or_none(row.get("path")),
        status=_str_or_none(row.get("status")),
        error=_str_or_none(row.get("error")),
    )


def _to_trace_summary(trace: dict[str, Any]) -> TraceSummary:
    spans = trace.get("spans", []) if isinstance(trace.get("spans"), list) else []
    processes = trace.get("processes", {}) if isinstance(trace.get("processes"), dict) else {}
    trace_id = str(spans[0].get("traceID", "")) if spans and isinstance(spans[0], dict) else ""

    root_span: dict[str, Any] | None = None
    for span in spans:
        if not isinstance(span, dict):
            continue
        references = span.get("references", [])
        if not references:
            root_span = span
            break
    if root_span is None and spans and isinstance(spans[0], dict):
        root_span = spans[0]

    service_names = sorted(
        {
            str(process.get("serviceName"))
            for process in processes.values()
            if isinstance(process, dict) and process.get("serviceName")
        }
    )

    duration_us = int(sum(int(span.get("duration", 0)) for span in spans if isinstance(span, dict))) if spans else None
    start_time_us = int(root_span.get("startTime", 0)) if root_span else None

    return TraceSummary(
        trace_id=trace_id,
        root_operation=str(root_span.get("operationName")) if root_span else None,
        span_count=len(spans),
        start_time_us=start_time_us,
        duration_us=duration_us,
        services=service_names,
    )


def _to_trace_span(span: dict[str, Any], processes: dict[str, Any]) -> TraceSpan:
    process_id = span.get("processID")
    process = processes.get(process_id, {}) if isinstance(processes, dict) else {}
    tags = span.get("tags", []) if isinstance(span.get("tags"), list) else []

    status_code: str | None = None
    error_flag: str | None = None
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        key = str(tag.get("key", ""))
        value = _str_or_none(tag.get("value"))
        if key == "http.response.status_code":
            status_code = value
        elif key == "error":
            error_flag = value

    parent_span_id: str | None = None
    references = span.get("references", []) if isinstance(span.get("references"), list) else []
    for ref in references:
        if isinstance(ref, dict) and ref.get("refType") == "CHILD_OF":
            parent_span_id = _str_or_none(ref.get("spanID"))
            break

    return TraceSpan(
        span_id=str(span.get("spanID", "")),
        parent_span_id=parent_span_id,
        operation=str(span.get("operationName", "")),
        service=_str_or_none(process.get("serviceName") if isinstance(process, dict) else None),
        duration_ms=round(float(span.get("duration", 0)) / 1000.0, 3),
        status_code=status_code,
        error=error_flag,
    )


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
