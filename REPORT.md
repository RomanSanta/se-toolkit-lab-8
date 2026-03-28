# Lab 8 — Report

Paste your checkpoint evidence below. Add screenshots as image files in the repo and reference them with `![description](path)`.

## Task 1A — Bare agent

<!-- Paste the agent's response to "What is the agentic loop?" and "What labs are available in our LMS?" -->

## Task 1B — Agent with LMS tools

<!-- Paste the agent's response to "What labs are available?" and "Describe the architecture of the LMS system" -->

## Task 1C — Skill prompt

<!-- Paste the agent's response to "Show me the scores" (without specifying a lab) -->

## Task 2A — Deployed agent

`docker compose --env-file .env.docker.secret ps`:

```text
se-toolkit-lab-8-nanobot-1   ...   Up ...
se-toolkit-lab-8-caddy-1     ...   Up ... 0.0.0.0:42002->80/tcp
```

`docker compose --env-file .env.docker.secret logs nanobot --tail 50` excerpt:

```text
Using config: /app/nanobot/config.resolved.json
Starting nanobot gateway version 0.1.4.post5 on port 18790...
Channels enabled: webchat
MCP server 'lms': connected, 9 tools registered
MCP server 'webchat': connected, 1 tools registered
Agent loop started
```

## Task 2B — Web client

Caddy serves Flutter UI:

```text
$ curl http://localhost:42002/flutter
HTTP 200
<!DOCTYPE html>
<html>
<head>
  <base href="/flutter/">
```

WebSocket endpoint through Caddy returns real backend data:

```text
$ uv run python (websocket probe to ws://localhost:42002/ws/chat?access_key=...)
{"type":"text","content":"Available labs from the LMS backend:
1. Lab 01 – Products, Architecture & Roles
2. Lab 02 — Run, Fix, and Deploy a Backend Service
3. Lab 03 — Backend API: Explore, Debug, Implement, Deploy
4. Lab 04 — Testing, Front-end, and AI Agents
5. Lab 05 — Data Pipeline and Analytics Dashboard
6. Lab 06 — Build Your Own Agent
7. Lab 07 — Build a Client with an AI Coding Agent
8. lab-08","format":"markdown"}
```

## Task 3A — Structured logging

Happy-path backend log excerpt (`trace_id=99c866c0b11e34c837180382add298a1`):

```text
2026-03-28 10:37:06,079 INFO ... trace_id=99c866c0b11e34c837180382add298a1 ... - request_started
2026-03-28 10:37:06,080 INFO ... trace_id=99c866c0b11e34c837180382add298a1 ... - db_query
2026-03-28 10:37:06,085 INFO ... trace_id=99c866c0b11e34c837180382add298a1 ... - request_completed
INFO: ... "GET /items/ HTTP/1.1" 200 OK
```

Error-path backend log excerpt (`trace_id=90d5fdfecc2b1ac0812b6f82a015fb78`, with postgres stopped):

```text
2026-03-28 10:45:42,482 INFO ... trace_id=90d5fdfecc2b1ac0812b6f82a015fb78 ... - request_started
2026-03-28 10:45:42,486 INFO ... trace_id=90d5fdfecc2b1ac0812b6f82a015fb78 ... - db_query
2026-03-28 10:45:42,631 ERROR ... trace_id=90d5fdfecc2b1ac0812b6f82a015fb78 ... - db_query
2026-03-28 10:45:42,633 INFO ... trace_id=90d5fdfecc2b1ac0812b6f82a015fb78 ... - request_completed
INFO: ... "GET /items/ HTTP/1.1" 404 Not Found
```

VictoriaLogs query evidence:

```text
_time:10m service.name:"Learning Management Service" severity:ERROR
```

```text
$ curl "http://localhost:42010/select/logsql/query?query=_time:10m%20service.name:%22Learning%20Management%20Service%22%20severity:ERROR&limit=5"
{"_time":"2026-03-28T10:45:42.631774976Z", "event":"db_query", "severity":"ERROR", "trace_id":"90d5fdfecc2b1ac0812b6f82a015fb78", ...}
```

## Task 3B — Traces

Healthy trace evidence (`trace_id=99c866c0b11e34c837180382add298a1`):

```text
$ curl "http://localhost:42011/select/jaeger/api/traces/99c866c0b11e34c837180382add298a1"
span_count: 8
operations: ["GET /items/", "SELECT db-lab-8", "connect", "BEGIN;", "ROLLBACK;", ...]
```

Error trace evidence (`trace_id=90d5fdfecc2b1ac0812b6f82a015fb78`):

```text
$ curl "http://localhost:42011/select/jaeger/api/traces/90d5fdfecc2b1ac0812b6f82a015fb78"
span_count: 5
operations: ["GET /items/", "connect", "GET /items/ http send", ...]
```

## Task 3C — Observability MCP tools

Agent response under normal conditions:

```text
Any LMS backend errors in the last 10 minutes?
=> LMS backend has 1 ERROR log event(s) in the last 10 minutes. Latest error: event=db_query, time=2026-03-28T10:37:37.568976896Z. Trace 7b652999bd9ea78982572857f7e788d5 has 6 spans.
```

Agent response after stopping PostgreSQL and triggering LMS-backed requests:

```text
Any LMS backend errors in the last 10 minutes?
=> LMS backend has 3 ERROR log event(s) in the last 10 minutes. Latest error: event=db_query, time=2026-03-28T10:45:42.631774976Z. Trace 90d5fdfecc2b1ac0812b6f82a015fb78 has 5 spans.
```

## Task 4A — Multi-step investigation

With PostgreSQL stopped, agent response to `What went wrong?`:

```text
I found recent LMS backend errors (count=3) from logs. Latest log evidence: event=db_query, time=2026-03-28T11:02:22.991054336Z, error='[Errno -2] Name or service not known'. Trace 373043a6907abd18fe0796c9272a8ef5 has 5 spans; root operation looks like 'GET /items/'.
```

## Task 4B — Proactive health check

Transcript of proactive report (while failure was present and postgres was stopped):

```text
LMS backend has 1 ERROR log event(s) in the last 2 minutes. Latest error: event=db_query, time=2026-03-28T11:03:36.937530112Z. Trace 00393adea4ccefaa8e6b74b6e5269543 has 5 spans.
```

## Task 4C — Bug fix and recovery

1. Root cause identified:
- Planted bug in `backend/src/lms_backend/routers/items.py` (`get_items`).
- A broad `except Exception` converted real DB failures into `404 Items not found`, hiding the true cause.

2. Code fix (description):
- Removed the broad exception mapping in `get_items` and let real exceptions propagate to the global handler.
- Result: failure path now surfaces real backend/db errors (HTTP 500) instead of false 404.

3. Post-fix failure check (`What went wrong?` after redeploy, with postgres stopped):

```text
I found recent LMS backend errors (count=6) from logs. Latest log evidence: event=unhandled_exception, time=2026-03-28T11:07:11.77716736Z, error='no error text'. Trace c3342daf3e52a7f1b68d3931a1cf70e8 has 4 spans; root operation looks like 'GET /items/'.
```

Backend log confirms post-fix status is now 500 (not 404):

```text
... trace_id=c3342daf3e52a7f1b68d3931a1cf70e8 ... event=db_query (ERROR)
... event=unhandled_exception ...
GET /items/ HTTP/1.1" 500 Internal Server Error
```

4. Healthy follow-up (after postgres restart):

```text
No LMS backend ERROR logs found in the last 2 minutes. System looks healthy in this window.
```
