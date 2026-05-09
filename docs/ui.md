# Web UI

The web UI is a React + Vite single-page application served by the FastAPI backend.

**URLs:**
- Docker Compose: `http://localhost` (frontend on port 80, backend on port 8000)
- Local dev: `http://localhost:5173` (Vite dev server with HMR)

---

## Chat page

The main investigation interface.

**Input area** — type a message and press Enter or click Send. The agent starts
streaming its response immediately. A Stop button cancels an in-flight request mid-stream.

**Streaming response** — agent tokens appear in real time as the LLM reasons.
Tool calls appear as collapsible cards as they complete, showing the tool name,
arguments, and result. A contextual status label ("Digging through CloudTrail…",
"Checking Lambda metrics…") appears while each tool runs.

**Tool call inspector** — each tool call card is collapsed by default; click to expand
and see the full arguments and result JSON.

**Cost card** — after each agent response, a collapsible card shows:
- Input tokens / Output tokens
- Per-component USD cost breakdown
- Total cost for the turn
- Latency in milliseconds

**Session continuity** — the session ID is stored in the URL. Refreshing the page
or sharing the URL resumes the same conversation from where it left off (SQLite/Postgres
backends only — memory backend loses history on restart).

---

## Session history sidebar

Lists all past sessions sorted by last activity. Each entry shows:
- Session title (first user message, truncated)
- Time since last active (relative, e.g. "3 hours ago")
- Model used

**Actions:**
- Click any session to load it in the chat view with full history restored
- **New chat** button starts a fresh session with a new UUID
- **Delete** (trash icon) soft-deletes the session — it disappears from the list
  immediately but data is preserved in the database

---

## History page

Accessible from the sidebar. Shows a searchable list of all past sessions.

**Search** — filters sessions by keyword matching the title or any user message.
Results show a short content snippet from the first matching message.

**Session list** — displays title, last active time, model, and a content snippet.
Click any row to open the session in the chat page.

---

## Dashboard page

See [`dashboard.md`](dashboard.md) for full details on each panel.

---

## Settings page

Shows the active configuration fetched in real time from `GET /settings`. Three tabs:

**Environment** — all env vars with their live values. Sensitive fields (`LLM_API_KEY`,
`DATABASE_URL`, `JWT_SECRET`, etc.) are masked by default; click the eye icon to reveal
the truncated preview. Non-sensitive fields (`LLM_MODEL`, `AWS_REGION`, etc.) are shown
as-is.

**Agent config** — agent behaviour settings: max tool calls, timeout, tool response cap,
summarization threshold, poll interval.

**Integrations** — Slack, GitHub, PagerDuty, Datadog connection stubs (not yet wired up).

Settings are read-only — change values by editing `.env` and restarting the server.

---

## Login page

Shown when `JWT_SECRET` is set in `.env`. Accessible at `/login`.

- **Register tab** — create the first account (auto-admin) or subsequent accounts
- **Login tab** — email + password; stores the JWT in `localStorage` on success

If auth is disabled (`JWT_SECRET` unset), the login page is skipped entirely and all
users get full access.

---

## Team page

Admin-only. Accessible from the sidebar (hidden for `user` role). Shows all registered
users in a table with name, email, role, and created date.

- **Add user** — create a new user with email, name, password, and role
- **Change role** — inline dropdown to promote/demote between `admin` and `user`
- **Delete user** — removes the account immediately

Non-admins who navigate to `/users` see an "Admin access required" message instead of
the table.

---

## Dark mode

The UI respects the system dark/light mode preference automatically. No toggle is needed.

---

## Theme and design

- Font: system monospace stack
- Framework: React 18 + Tailwind CSS
- Icons: Lucide React
- Build tool: Vite with HMR in development
