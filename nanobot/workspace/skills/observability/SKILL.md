---
name: observability
description: Investigate LMS issues with logs and traces via obs MCP tools
always: true
---

# Observability Skill

Use observability tools for requests about errors, failures, incidents, latency,
"what went wrong", or system health checks.

## Tool map

- `logs_error_count`: count recent ERROR records by service.
- `logs_search`: inspect recent log records and extract `trace_id`.
- `traces_list`: list fresh traces for a specific service.
- `traces_get`: inspect one trace in detail by ID.
- `cron`: create/list/remove recurring health checks for the current chat.

## Investigation Strategy

- For "What went wrong?" or "Check system health", run a one-pass chain:
  1. `logs_error_count` for a fresh window.
  2. `logs_search` scoped to `Learning Management Service` for recent ERROR events.
  3. extract a recent `trace_id` and call `traces_get`.
  4. respond with one concise diagnosis citing both log and trace evidence.
- Explicitly mention mismatches like "DB failure in logs/traces but HTTP 404 in response".
- Prefer narrow windows (2-10 minutes) for fresh incidents.

## Proactive checks (cron)

- When asked to create a recurring health check in chat, use `cron` with `action="add"`.
- For a 2-minute check, use `every_seconds=120`.
- Use a message that checks LMS/backend errors in the last 2 minutes, inspects trace if needed, and reports briefly.
- Use `cron` `action="list"` when user asks for scheduled jobs.
- Use `cron` `action="remove"` when user asks to remove the test job.

## Response style

- Keep summaries short and operational.
- Include: affected service, error count, freshest timestamp, likely failing route/operation, and one next action.
- If no recent errors are found, state explicitly: system looks healthy for the checked window.
