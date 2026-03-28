---
name: lms
description: Use LMS MCP tools for live course data
always: true
---

# LMS Skill

Use LMS MCP tools for any request about labs, learners, health, scores, pass rates, completion, groups, timeline, or top learners.

## Tool map

- `lms_health`: backend health and item count.
- `lms_labs`: list available labs and lab metadata.
- `lms_learners`: list learners.
- `lms_pass_rates`: average score and attempts for a lab.
- `lms_completion_rate`: passed vs total for a lab.
- `lms_groups`: average score and student count per group for a lab.
- `lms_timeline`: submissions over time for a lab.
- `lms_top_learners`: top performers for a lab.
- `lms_sync_pipeline`: trigger LMS sync when data looks missing or stale.

## Strategy

- For LMS questions, prefer tools over guessing.
- If the user asks for scores, pass rates, completion, groups, timeline, or top learners without a lab, call `lms_labs` first.
- If multiple labs are available, ask the user to choose one. Use each lab title as the default user-facing label unless a better identifier is provided.
- Let the shared `structured-ui` skill decide how to present the choice on channels that support interactive UI.
- If `lms_labs` returns no labs, trigger `lms_sync_pipeline`, then retry `lms_labs`.
- If a tool call fails, explain the failure briefly and suggest the shortest actionable retry.

## Response style

- Keep answers concise and factual.
- Format percentages with one decimal place (for example, `73.4%`) and include raw counts when available.
- For rankings, show numbered results with the key metric.
- For "what can you do?", clearly explain current LMS capabilities and limits: can answer only through available `lms_*` tools and current backend data.
