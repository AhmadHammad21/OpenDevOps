# OpenDevOps App UI Kit

## Overview
High-fidelity interactive prototype of the OpenDevOps web application. Built with React + inline JSX, no build step required.

## Design language
- **Style:** Light + minimal (Linear/Vercel-inspired)
- **Accent:** Indigo `#6366F1`
- **Font:** Geist Sans (UI) + Geist Mono (code/terminal)
- **Icons:** Lucide-style inline SVGs (1.75px stroke)

## Screens covered
| Screen | File | Description |
|---|---|---|
| Login / Onboarding | `Login.jsx` | Email + GitHub OAuth, 3-step onboarding |
| Dashboard | `Dashboard.jsx` | Stats, agent status cards, recent pipeline runs |
| Chat | `ChatInterface.jsx` | Claude-style sidebar + message thread + agent command output |
| Pipelines | `Pipelines.jsx` | Pipeline list with expandable step visualization |
| Agent Logs | `AgentLogs.jsx` | Terminal log viewer with level filtering |
| Settings | `Settings.jsx` | Env vars editor, agent config, integrations, notifications |
| Admin | `AdminPanel.jsx` | Team members, roles, audit log |

## Component files
- `Shared.jsx` — tokens, Icon, Badge, Btn, Avatar (load first)
- `Sidebar.jsx` — navigation sidebar
- `Dashboard.jsx` — dashboard screen
- `ChatInterface.jsx` — chat screen
- `Settings.jsx` — settings screen
- `AdminPanel.jsx` — admin screen
- `AgentLogs.jsx` — logs screen
- `Pipelines.jsx` — pipelines screen
- `Login.jsx` — auth/onboarding screen
- `index.html` — entry point, assembles all screens

## Usage
Open `index.html` in a browser. Use the **Tweaks** toolbar toggle to switch pages and explore accent colors.

## Notes
- No real backend — all data is static/fake
- GitHub repo not yet attached; will be updated once provided
