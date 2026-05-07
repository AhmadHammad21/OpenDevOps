# Dashboard

The dashboard is available at `http://localhost` (Docker) or `http://localhost:5173`
(local dev). It shows aggregated analytics across all sessions and requires SQLite or
Postgres — the memory backend returns live counts only (lost on restart).

All data comes from `GET /stats`.

---

## Stat cards (top row)

| Card | What it shows |
|---|---|
| **Sessions** | Total non-deleted sessions |
| **Tool calls** | Total tool calls across all sessions · avg per session · error % |
| **Total cost** | Sum of `cost_usd` from all usage events · total tokens (input + output) |
| **Avg latency** | Average response latency in seconds · total query count |

## Context management row

Appears only when at least one summarization has fired.

| Card | What it shows |
|---|---|
| **Sessions compacted** | Number of times conversation summarization ran |
| **Context saved** | Estimated tokens recovered (`chars_compacted / 4`) · raw char count |

See [`conversation_summarization.md`](conversation_summarization.md) for how this data is collected.

## Activity chart

Bar chart of session count per day over the last 14 days. Hover any bar for the
exact date and count. Empty days render as a thin grey bar.

## Calls by service

Horizontal bar chart showing how many tool calls each AWS service received, as a
percentage of total tool calls. Services: CloudWatch, Lambda, CloudTrail, RDS, ECS,
EC2, IAM, Agent (= `submit_investigation` calls).

## Recurring incident types

Shows the distribution of root cause categories across all completed investigations
(sessions where `submit_investigation` was called with a `root_cause_category`):

| Category | Colour |
|---|---|
| System change | Amber |
| Input anomaly | Blue |
| Resource limit | Orange |
| Component failure | Red |
| Dependency issue | Purple |
| Unknown | Grey |

## Top tools (no UI panel — API only)

`GET /stats` returns a `top_tools` list (up to 12 entries) with call count and error
count per tool. Not currently rendered in the UI but available for custom dashboards
or monitoring.

## Recent sessions

Last 6 sessions sorted by `last_active_at`, showing title, model, query count, tool
call count, and cost. Click any row to open the session in the chat page.

---

## Data source

All dashboard data comes from three tables:

| Table | Used for |
|---|---|
| `sessions` | Session counts, activity chart, recent sessions |
| `tool_calls` | Tool call counts, error counts, service breakdown, root causes |
| `usage_events` | Token counts, cost, latency, summarization stats |

See [`schema.md`](schema.md) for full table definitions.
