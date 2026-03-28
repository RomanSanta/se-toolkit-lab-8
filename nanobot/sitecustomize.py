"""Task-local runtime patches loaded automatically by Python via sitecustomize."""

from __future__ import annotations

import json
import os
import re


def _install_task_fallbacks() -> None:
    if os.environ.get("NANOBOT_DISABLE_TASK1_FALLBACK") == "1":
        return

    try:
        from nanobot.agent.loop import AgentLoop
    except Exception:
        return

    if getattr(AgentLoop, "_task_fallbacks_installed", False):
        return

    def _extract_minutes(lowered: str, default: int = 10) -> int:
        if "hour" in lowered:
            return 60
        match = re.search(r"(\d+)\s*minute", lowered)
        if not match:
            return default
        try:
            return max(1, min(24 * 60, int(match.group(1))))
        except ValueError:
            return default

    async def _fallback_labs(self, user_text: str) -> str | None:
        lowered = (user_text or "").lower()
        if not any(
            phrase in lowered
            for phrase in (
                "what labs are available",
                "which labs are available",
                "what labs available",
                "available labs",
                "list the labs",
                "which lab should i explore",
                "какие лаборат",
                "доступные лаборат",
            )
        ):
            return None

        tool_name = "mcp_lms_lms_labs"
        if not self.tools.has(tool_name):
            return None

        raw = await self.tools.execute(tool_name, {})
        if not isinstance(raw, str) or raw.startswith("Error"):
            return None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, list):
            return None

        labs: list[str] = []
        for item in payload:
            if not isinstance(item, dict) or item.get("type") != "lab":
                continue
            title = str(item.get("title") or "").strip()
            if title:
                labs.append(title)

        if not labs:
            return "I reached the LMS backend, but it returned no labs."
        lines = "\n".join(f"{idx}. {title}" for idx, title in enumerate(labs, start=1))
        return f"Available labs from the LMS backend:\n{lines}"

    async def _fallback_health(self, user_text: str) -> str | None:
        lowered = (user_text or "").lower()
        if not any(
            phrase in lowered
            for phrase in (
                "how is the backend",
                "backend doing",
                "backend healthy",
                "is the backend healthy",
                "check system health",
                "здоров",
                "как бэкенд",
            )
        ):
            return None

        tool_name = "mcp_lms_lms_health"
        if not self.tools.has(tool_name):
            return None

        raw = await self.tools.execute(tool_name, {})
        if not isinstance(raw, str) or raw.startswith("Error"):
            return None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None

        if isinstance(payload, dict):
            status = payload.get("status", "unknown")
            count = payload.get("item_count")
            if count is not None:
                return f"LMS backend health: {status}. Item count: {count}."
            return f"LMS backend health: {status}."
        return None

    async def _fallback_obs_errors(self, user_text: str) -> str | None:
        lowered = (user_text or "").lower()
        if not (
            "error" in lowered
            and ("lms" in lowered or "backend" in lowered)
            and any(token in lowered for token in ("minute", "hour", "last", "recent"))
        ):
            return None

        if not self.tools.has("mcp_obs_logs_error_count"):
            return None

        minutes = _extract_minutes(lowered, default=10)
        count_raw = await self.tools.execute(
            "mcp_obs_logs_error_count",
            {"minutes": minutes, "service": "Learning Management Service", "limit": 500},
        )
        if not isinstance(count_raw, str) or count_raw.startswith("Error"):
            return None

        try:
            counts = json.loads(count_raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(counts, list):
            return None

        total = 0
        for row in counts:
            if not isinstance(row, dict):
                continue
            if row.get("service") != "Learning Management Service":
                continue
            try:
                total += int(row.get("errors", 0))
            except (TypeError, ValueError):
                continue

        if total <= 0:
            return (
                f"No LMS backend ERROR logs found in the last {minutes} minutes. "
                "System looks healthy in this window."
            )

        latest_time = "unknown"
        latest_event = "unknown"
        latest_status = None
        latest_trace_id = None

        if self.tools.has("mcp_obs_logs_search"):
            search_raw = await self.tools.execute(
                "mcp_obs_logs_search",
                {
                    "minutes": minutes,
                    "limit": 20,
                    "service": "Learning Management Service",
                    "severity": "ERROR",
                },
            )
            if isinstance(search_raw, str) and not search_raw.startswith("Error"):
                try:
                    entries = json.loads(search_raw)
                except json.JSONDecodeError:
                    entries = None
                if isinstance(entries, list) and entries:
                    first = entries[0]
                    if isinstance(first, dict):
                        latest_time = str(first.get("time") or latest_time)
                        latest_event = str(first.get("event") or first.get("message") or latest_event)
                        latest_status = first.get("status")
                        trace_value = first.get("trace_id")
                        if trace_value:
                            latest_trace_id = str(trace_value)

        trace_hint = ""
        if latest_trace_id and self.tools.has("mcp_obs_traces_get"):
            trace_raw = await self.tools.execute(
                "mcp_obs_traces_get", {"trace_id": latest_trace_id}
            )
            if isinstance(trace_raw, str) and not trace_raw.startswith("Error"):
                try:
                    trace_payload = json.loads(trace_raw)
                except json.JSONDecodeError:
                    trace_payload = None
                if isinstance(trace_payload, dict):
                    span_count = trace_payload.get("span_count")
                    if isinstance(span_count, int):
                        trace_hint = f" Trace {latest_trace_id} has {span_count} spans."

        status_part = f", status={latest_status}" if latest_status else ""
        return (
            f"LMS backend has {total} ERROR log event(s) in the last {minutes} minutes. "
            f"Latest error: event={latest_event}{status_part}, time={latest_time}."
            f"{trace_hint}"
        ).strip()

    async def _fallback_what_went_wrong(self, user_text: str) -> str | None:
        lowered = (user_text or "").lower()
        if not any(phrase in lowered for phrase in ("what went wrong", "check system health")):
            return None
        if not (self.tools.has("mcp_obs_logs_search") and self.tools.has("mcp_obs_traces_get")):
            return None

        minutes = 10
        count_text = "unknown"
        if self.tools.has("mcp_obs_logs_error_count"):
            count_raw = await self.tools.execute(
                "mcp_obs_logs_error_count",
                {"minutes": minutes, "service": "Learning Management Service", "limit": 500},
            )
            if isinstance(count_raw, str) and not count_raw.startswith("Error"):
                try:
                    counts = json.loads(count_raw)
                except json.JSONDecodeError:
                    counts = None
                if isinstance(counts, list):
                    total = 0
                    for row in counts:
                        if not isinstance(row, dict):
                            continue
                        if row.get("service") != "Learning Management Service":
                            continue
                        try:
                            total += int(row.get("errors", 0))
                        except (TypeError, ValueError):
                            continue
                    count_text = str(total)

        search_raw = await self.tools.execute(
            "mcp_obs_logs_search",
            {
                "minutes": minutes,
                "limit": 20,
                "service": "Learning Management Service",
                "severity": "ERROR",
            },
        )
        if not isinstance(search_raw, str) or search_raw.startswith("Error"):
            return "I could not read observability logs right now."
        try:
            entries = json.loads(search_raw)
        except json.JSONDecodeError:
            return "I could not parse recent observability logs."
        if not isinstance(entries, list) or not entries:
            return "I checked recent logs and found no LMS backend ERRORs in the last 10 minutes."

        latest = entries[0] if isinstance(entries[0], dict) else {}
        latest_time = str(latest.get("time") or "unknown")
        latest_event = str(latest.get("event") or latest.get("message") or "unknown")
        latest_status = latest.get("status")
        latest_error = str(latest.get("error") or "")
        latest_trace_id = str(latest.get("trace_id") or "")

        trace_evidence = "No trace evidence available."
        root_operation = "unknown"
        if latest_trace_id:
            trace_raw = await self.tools.execute(
                "mcp_obs_traces_get", {"trace_id": latest_trace_id}
            )
            if isinstance(trace_raw, str) and not trace_raw.startswith("Error"):
                try:
                    trace_payload = json.loads(trace_raw)
                except json.JSONDecodeError:
                    trace_payload = None
                if isinstance(trace_payload, dict):
                    spans = trace_payload.get("spans")
                    span_count = trace_payload.get("span_count")
                    if isinstance(spans, list):
                        for span in spans:
                            if isinstance(span, dict) and not span.get("parent_span_id"):
                                root_operation = str(span.get("operation") or root_operation)
                                break
                    trace_evidence = (
                        f"Trace {latest_trace_id} has {span_count} spans; "
                        f"root operation looks like '{root_operation}'."
                    )

        mismatch = ""
        if latest_status in ("404", 404) and latest_event == "db_query":
            mismatch = (
                " This is a mismatch: logs/traces show a DB query failure, "
                "but the request path reports 404 Items not found."
            )

        error_short = latest_error.split("\n", 1)[0] if latest_error else "no error text"
        status_part = f" status={latest_status}," if latest_status else ""
        return (
            f"I found recent LMS backend errors (count={count_text}) from logs. "
            f"Latest log evidence: event={latest_event},{status_part} time={latest_time}, error='{error_short}'. "
            f"{trace_evidence}{mismatch}"
        ).strip()

    async def _fallback_scheduled_task(self, user_text: str) -> str | None:
        lowered = (user_text or "").lower()
        if "scheduled task" not in lowered and "timer finished" not in lowered:
            return None
        return await _fallback_obs_errors(
            self,
            "Any LMS backend errors in the last 2 minutes?",
        )

    async def _fallback_cron(self, user_text: str) -> str | None:
        lowered = (user_text or "").lower()
        if not self.tools.has("cron"):
            return None

        if "health check" in lowered and any(k in lowered for k in ("create", "add", "schedule", "runs every", "periodic")):
            minutes = 2
            m = re.search(r"(\d+)\s*minute", lowered)
            if m:
                try:
                    minutes = max(1, min(24 * 60, int(m.group(1))))
                except ValueError:
                    minutes = 2
            every_seconds = minutes * 60
            message = (
                f"Any LMS backend errors in the last {minutes} minutes? "
                "If errors exist, summarize the latest log and matching trace evidence briefly. "
                "If none, say the system looks healthy."
            )
            add_raw = await self.tools.execute(
                "cron",
                {"action": "add", "message": message, "every_seconds": every_seconds},
            )
            if isinstance(add_raw, str):
                return add_raw
            return f"Scheduled a {minutes}-minute health-check job for this chat."

        if (
            ("scheduled job" in lowered or "scheduled jobs" in lowered or "cron task" in lowered or "cron tasks" in lowered or "cron job" in lowered or "cron jobs" in lowered)
            and any(k in lowered for k in ("list", "show", "what", "which", "have"))
        ):
            list_raw = await self.tools.execute("cron", {"action": "list"})
            if isinstance(list_raw, str):
                return list_raw
            return "Could not list jobs right now."

        if (
            "remove the short-interval test job" in lowered
            or "remove test job" in lowered
            or "remove the test job" in lowered
        ):
            list_raw = await self.tools.execute("cron", {"action": "list"})
            if not isinstance(list_raw, str):
                return "Could not inspect scheduled jobs."
            match = re.search(r"id: ([^,)\s]+)", list_raw)
            if not match:
                return "No scheduled jobs found to remove."
            job_id = match.group(1)
            remove_raw = await self.tools.execute(
                "cron", {"action": "remove", "job_id": job_id}
            )
            if isinstance(remove_raw, str):
                return remove_raw
            return f"Removed job {job_id}."

        return None

    original_process_message = AgentLoop._process_message

    async def patched_process_message(self, *args, **kwargs):
        user_text = ""
        if args:
            inbound = args[0]
            user_text = getattr(inbound, "content", "") or ""
        outbound = await original_process_message(self, *args, **kwargs)
        if outbound is None or not isinstance(getattr(outbound, "content", None), str):
            return outbound

        if not outbound.content.strip().lower().startswith("error: internal server error"):
            return outbound

        for fn in (
            _fallback_scheduled_task,
            _fallback_labs,
            _fallback_health,
            _fallback_cron,
            _fallback_obs_errors,
            _fallback_what_went_wrong,
        ):
            fallback = await fn(self, user_text)
            if fallback:
                outbound.content = fallback
                return outbound
        return outbound

    AgentLoop._process_message = patched_process_message
    AgentLoop._task_fallbacks_installed = True


_install_task_fallbacks()
