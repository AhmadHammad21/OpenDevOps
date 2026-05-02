# OpenDevOps Design System

## Overview

**OpenDevOps** is an open-source platform tool that deploys a DevOps Agent — an AI-powered assistant that automates, monitors, and orchestrates DevOps workflows. It bridges the gap between experienced DevOps engineers and teams who are newer to infrastructure, CI/CD, and deployment pipelines.

The product has two distinct UI surfaces:
1. **CLI / Terminal Interface** — Dark, terminal-inspired, for engineers who live in the command line
2. **Web App UI** — Light, minimal, Linear/Vercel-style for the dashboard, chat, settings, and admin surfaces

**Sources:** No external codebase or Figma provided at time of creation — design system built from first principles based on product description and user direction. The user intends to attach a GitHub repo later for comparison and iteration.

---

## Products / Surfaces

| Surface | Description |
|---|---|
| Dashboard | Metrics, agent status, pipeline health overview |
| Chat | Claude-style AI assistant for issuing DevOps commands in natural language |
| Settings | Environment variable manager, secrets, integrations |
| Admin | User management, permissions, org settings |
| Agent Logs | Terminal-style output for agent run history |
| Pipelines | Workflow/pipeline visualization |
| Login / Onboarding | Auth flow, first-run setup |

---

## CONTENT FUNDAMENTALS

### Tone
- **Approachable but precise.** OpenDevOps serves both experienced DevOps engineers and teams new to infrastructure. Copy never talks down, but also never hides behind jargon.
- **Active, direct voice.** Prefer action verbs. "Deploy agent" not "Agent deployment can be initiated."
- **Second-person ("you").** The product addresses the user directly. "Your pipelines", "your environment", "configure your agent."
- **Short sentences.** Especially in UI labels. Error messages are human — they explain what happened AND what to do next.
- **No emoji in UI.** Icons are used instead of emoji for functional communication.
- **Sentence case everywhere.** "Deploy new agent" not "Deploy New Agent" — only proper nouns and brand names are capitalized.
- **Terminal context = monospace, lowercase.** CLI commands, env var keys, log output use monospace and stay lowercase-dominant.

### Examples
- ✅ "Your agent is deploying. This usually takes ~30 seconds."
- ✅ "No pipelines yet. Connect your repo to get started."
- ✅ "Agent stopped — check your API_KEY environment variable."
- ❌ "The deployment process has been initiated successfully!"
- ❌ "ERROR: Pipeline Execution Failed Due To Configuration Issues"

---

## VISUAL FOUNDATIONS

### Color System
- **Primary palette:** Near-black backgrounds (`#0A0A0B`), neutral grays, pure white text — for the app UI
- **Accent:** Electric indigo (`#6366F1`) — modern, technical, stands out on both light and dark
- **Success:** Emerald green (`#10B981`) — pipelines passing, agents healthy
- **Warning:** Amber (`#F59E0B`) — degraded states, pending
- **Error/Danger:** Rose red (`#F43F5E`) — failures, critical alerts
- **Terminal surface:** True dark `#0D1117` (GitHub-dark inspired), green terminal text `#3FB950`

### Typography
- **UI Sans:** Geist Sans (Google Fonts) — geometric, clean, built for developer tools
- **Code/Mono:** Geist Mono — natural pairing for terminal output, env vars, code
- **Scale:** 11px (micro labels) → 12px → 14px (body) → 16px → 20px → 24px → 32px → 48px (hero)
- **Weight range:** 400 (body), 500 (UI labels), 600 (headings), 700 (display)

### Spacing
- **Base unit:** 4px. Scale: 4, 8, 12, 16, 24, 32, 48, 64, 80, 96
- **Component padding:** Buttons 8×16px (sm), 10×20px (md), 12×24px (lg)
- **Sidebar width:** 240px (expanded), 56px (collapsed)
- **Content max-width:** 1200px

### Backgrounds
- **Light UI:** `#FFFFFF` base, `#F9FAFB` page bg, `#F3F4F6` subtle surfaces
- **Dark terminal:** `#0D1117` base, `#161B22` elevated, `#21262D` borders
- **No gradients in UI** — flat surfaces only; gradients only used for subtle hero/landing sections
- **No full-bleed imagery** in app UI — data and components fill the space

### Cards
- Light UI: white background, 1px `#E5E7EB` border, `border-radius: 8px`, subtle `box-shadow: 0 1px 3px rgba(0,0,0,0.07)`
- Dark terminal: `#161B22` bg, 1px `#30363D` border, same 8px radius, no shadow

### Borders & Radius
- Buttons: `border-radius: 6px`
- Cards/panels: `border-radius: 8px`
- Modals/dialogs: `border-radius: 12px`
- Inputs: `border-radius: 6px`
- Badges/chips: `border-radius: 4px`
- Full pill (toggles, tags): `border-radius: 9999px`

### Shadows (Light UI)
- `--shadow-xs`: `0 1px 2px rgba(0,0,0,0.05)`
- `--shadow-sm`: `0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)`
- `--shadow-md`: `0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.04)`
- `--shadow-lg`: `0 10px 15px rgba(0,0,0,0.08), 0 4px 6px rgba(0,0,0,0.04)`

### Animation
- **Easing:** `cubic-bezier(0.16, 1, 0.3, 1)` (snappy ease-out) for entrances; `ease` for micro-interactions
- **Duration:** 120ms (micro), 180ms (UI transitions), 280ms (panel slides), 400ms (page transitions)
- **Sidebar collapse:** slide + fade, 280ms
- **No bounces** — professional, controlled motion only
- **Terminal output:** character-by-character typewriter effect for agent log streaming

### Hover / Press States
- **Buttons:** background lightens/darkens 8%; no outline change
- **Sidebar items:** `#F3F4F6` bg on hover (light), `#1C2128` on hover (dark)
- **Cards:** subtle shadow lift on hover (`--shadow-md`)
- **Destructive actions:** hover shifts to rose background
- **Press:** `scale(0.98)` + 50ms transition

### Iconography
See ICONOGRAPHY section below.

### Layout
- **Sidebar-based app shell:** fixed left sidebar (240px), top nav bar (56px), main content area
- **Chat layout:** sidebar left (conversations), main panel (message thread), no right panel by default
- **Dashboard:** CSS Grid, 12-column, responsive breakpoints at 768px and 1200px

### Use of Transparency & Blur
- Sidebar overlays on mobile: `backdrop-filter: blur(8px)` with semi-transparent overlay
- Dropdown menus: slight blur on dark surfaces
- No frosted glass in main UI — reserved for modals only

---

## ICONOGRAPHY

**Icon library:** Lucide Icons (CDN) — thin stroke, 1.5px, clean geometric, excellent coverage for DevOps concepts (server, terminal, git-branch, settings, users, etc.)

- **Usage:** 16px (inline/labels), 20px (sidebar nav), 24px (section headers), 32px (empty states)
- **Stroke weight:** 1.5px (Lucide default)
- **Color:** inherits from text color — never hardcoded icon colors except status indicators
- **No emoji used as icons**
- **No PNG icons** — SVG/icon font only
- **No custom hand-drawn illustrations** at launch

---

## File Index

```
README.md                    — This file; full design system documentation
SKILL.md                     — Agent skill definition for Claude Code
colors_and_type.css          — All CSS custom properties (colors, type, spacing, shadows)
assets/
  logo.svg                   — OpenDevOps wordmark (placeholder)
  logo-mark.svg              — Icon-only mark
  logo-dark.svg              — Light version for dark backgrounds
fonts/
  (Google Fonts loaded via CDN — Geist Sans + Geist Mono)
preview/
  colors-brand.html          — Brand color swatches
  colors-neutral.html        — Neutral/gray scale
  colors-semantic.html       — Semantic status colors
  colors-dark.html           — Dark/terminal palette
  type-scale.html            — Typography scale specimen
  type-mono.html             — Monospace / code type specimen
  spacing-tokens.html        — Spacing + border radius tokens
  shadows-elevation.html     — Shadow system
  components-buttons.html    — Button variants
  components-inputs.html     — Form inputs
  components-badges.html     — Badges, chips, status indicators
  components-cards.html      — Card variants
  components-nav.html        — Sidebar navigation component
  components-terminal.html   — Terminal / log output component
ui_kits/
  app/
    README.md                — App UI kit notes
    index.html               — Full interactive prototype
    Sidebar.jsx              — Navigation sidebar
    TopNav.jsx               — Top navigation bar
    Dashboard.jsx            — Dashboard screen
    ChatInterface.jsx        — Chat / AI assistant
    Settings.jsx             — Settings & env variables
    AdminPanel.jsx           — Admin / user management
    AgentLogs.jsx            — Terminal log viewer
    Pipelines.jsx            — Pipeline visualization
    Login.jsx                — Auth / onboarding
```
