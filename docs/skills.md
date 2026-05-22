# Skills

Skills are on-demand investigation guides the agent can load during a session.
Each skill is a markdown file (`SKILL.md`) that contains step-by-step investigation
steps, key metrics to check, log patterns to look for, and a common root-cause table
for a specific incident type.

---

## How it works

1. At startup, the skill registry scans `src/skills/*/SKILL.md` and reads the
   frontmatter (name + description) from each file.
2. Available skill names and descriptions are injected into the agent's system prompt —
   this costs only a few tokens regardless of how many skills exist.
3. During an investigation, the agent calls `use_skill("lambda-throttling")` (or
   whichever name matches the incident). Only then is the full skill content loaded
   into the context window.
4. Unrelated skills cost **zero tokens** — their content is never loaded.

---

## Built-in skills

| Name | Description |
|---|---|
| `lambda-throttling` | Investigate Lambda function throttling — concurrency limits, burst limits, reserved concurrency misconfiguration |
| `ecs-deployment-failure` | Investigate an ECS service that won't stabilize — failed deployments, image pull errors, crashing or unhealthy tasks |
| `dynamodb-throttling` | Investigate DynamoDB throttling — provisioned capacity exceeded, hot partitions, GSI limits surfacing as upstream errors |
| `iam-permission-denied` | Investigate AccessDenied / not-authorized errors — recently changed role policies, missing permissions, trust policy issues |

---

## Adding a skill

1. Create a directory under `src/skills/` named after the incident type:
   ```
   src/skills/ecs-oom/
   ```

2. Create `SKILL.md` inside it with the required frontmatter:
   ```markdown
   ---
   name: ecs-oom
   description: Investigate ECS task out-of-memory crashes and container restarts
   ---

   ## ECS OOM Investigation

   ### Step 1 — Confirm OOM kills
   ...
   ```

3. Restart the server (or the CLI). The new skill is auto-discovered and injected
   into the system prompt — no code changes needed.

---

## Skill file format

```
src/skills/
└── <incident-type>/
    └── SKILL.md        ← required
```

**`SKILL.md` structure:**

```markdown
---
name: <slug used in use_skill() calls>
description: <one-line description shown in system prompt>
---

## Investigation steps go here
...
```

- `name` — must be unique; this is what the agent passes to `use_skill()`
- `description` — shown in the system prompt; keep it under 120 chars so it doesn't bloat the prompt
- Body — plain markdown; use headers, bullet lists, and tables freely

---

## Agent tools

Two tools are available to the agent:

| Tool | Description |
|---|---|
| `list_skills()` | Returns all skill names and descriptions |
| `use_skill(name)` | Loads the full skill content for the given name |

The agent typically calls `use_skill()` directly (names are already in the system
prompt) and only falls back to `list_skills()` if it needs to confirm what is available.

---

## Ideas for future skills

- `ecs-oom` — ECS container out-of-memory crashes
- `rds-high-connections` — RDS max connection limit exceeded
- `api-gateway-5xx` — API Gateway 5XX spike investigation
- `ec2-cpu-spike` — EC2 CPU utilisation runaway
- `lambda-cold-start` — Lambda cold start latency spikes
