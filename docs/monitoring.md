# Monitoring Dashboard

The Monitoring page shows a live feed of incidents detected by the event-driven consumer. Each entry is a completed investigation triggered by an AWS infrastructure event.

---

## Accessing the Dashboard

Navigate to **Monitoring** in the sidebar. The page is visible to all authenticated users; the data is shared org-wide.

---

## Incident Feed

Each alert card shows:

- **Confidence badge** — `HIGH` (red), `MEDIUM` (amber), or `LOW` (grey)
- **Service** — the affected AWS service and resource name
- **Error** — the root cause summary from the agent
- **Time** — when the event was detected
- **SNS badge** — shown if the finding was published to SNS

Alerts are sorted by most recent first. Click any card to open the Alert Detail page.

---

## Alert Detail Page

Shows the full investigation result for a single alert:

- Root cause in a highlighted panel
- Resolution steps (if the agent produced them)
- Timestamp and SNS notification status

### Investigate button

Opens a new chat session with a pre-seeded prompt:

```
Investigate this incident further:

Service: ECS / my-api
Error: Container OOM killed
Confidence: HIGH
Time: 2026-05-09T18:30:00Z

Please provide deeper root cause analysis, check related services,
and suggest preventive measures.
```

The prompt auto-submits when the chat page loads. Use this to drill deeper than the automated investigation or to explore related services.

---

## Service Health Panel

The top of the Monitoring page shows a summary of tracked services and their last-known status (`healthy`, `error`, `unknown`). Status is updated in-memory each time the event consumer processes an event for that service.

---

## API

The monitoring endpoints require authentication:

```
GET  /api/monitoring/alerts?limit=50   → list recent alerts
GET  /api/monitoring/alerts/{id}       → single alert detail
GET  /api/monitoring/services          → service health summary
```

---

## Source Files

| File | Purpose |
|---|---|
| `frontend/src/pages/MonitoringPage.tsx` | Live incident feed UI |
| `frontend/src/pages/AlertDetailPage.tsx` | Alert detail + investigate deeplink |
| `src/api/routers/monitoring.py` | REST endpoints (auth-protected) |
| `src/agent/monitor_store.py` | In-memory service status + alert persistence |
