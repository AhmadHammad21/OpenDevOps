# OpenDevOps Agent — Demo Scenarios

Reproducible AWS incidents for demoing / recording the agent. Each script breaks
something in **your** AWS account in a controlled, reversible way, then you point
the agent at it and watch it investigate.

Everything is read-only on the agent side — these scripts just create the broken
state. All resources are prefixed `opendevops-demo` and every script has a
`teardown` action.

> ⚠️ **These create real AWS resources.** Cost is a few cents for the Lambda/IAM/
> DynamoDB cases; the ECS (M3) case costs a little while running. **Always run
> `teardown`** when you're done. Use a sandbox/dev account.

---

## Prerequisites

```bash
# AWS creds via the standard chain; override region/profile as needed
export AWS_PROFILE=your-sandbox-profile      # PowerShell: $env:AWS_PROFILE="..."
export AWS_REGION=us-east-1                   # PowerShell: $env:AWS_REGION="..."

# Scripts use boto3 (already a project dependency), so run them with uv:
uv run python demos/aws/e1_lambda_throttled.py setup
uv run python demos/aws/e1_lambda_throttled.py teardown
```

The IAM identity running the **scripts** needs write access (create Lambda/IAM/
DynamoDB/ECS/S3). The IAM identity the **agent** uses only needs the read-only
Operational policy from [iam_setup.md](../../apps/documentation/iam_setup.md).

---

## Scenario index

| Tier | Script | Incident | Tools exercised |
|---|---|---|---|
| Easy | `e1_lambda_throttled.py` | Lambda fully throttled (reserved concurrency = 0) | `get_lambda_function_config` + `use_skill(lambda-throttling)` |
| Easy | `e2_lambda_crashing.py` | Unhandled exception / high error rate | `get_lambda_error_rate`, `get_log_events` |
| Easy | `e3_alarm_in_alarm.py` | CloudWatch alarm firing | `get_alarms`, `get_alarm_history`, `get_metric_data` |
| Mid ⭐ | `m1_bad_deploy.py` | Errors started right after a deploy | + `lookup_cloudtrail_events` (UpdateFunctionCode) |
| Mid | `m2_timeout_misconfig.py` | Timeout lowered to 1s, everything times out | config + logs + CloudTrail |
| Mid | `m3_ecs_wont_stabilize.py` | ECS service can't pull image | `list_ecs_clusters`, `describe_ecs_service` |
| Hard ⭐ | `h1_lambda_dynamodb_throttle.py` | Lambda errors = DynamoDB throttling downstream | logs + `run_bash_command` (describe-table) |
| Hard ⭐ | `h2_iam_permission_regression.py` | AccessDenied after a policy was detached | logs + `get_iam_role_policies` + CloudTrail |
| Hard | `h3_lambda_vpc_no_egress.py` | VPC Lambda can't reach the internet | logs + config (vpc_enabled) + reasoning |

⭐ = strongest demos (clearest "the agent found it" narrative).

Each script's docstring has the exact prompt to give the agent and what it should find.

---

## Suggested demo flow

1. `setup` the scenario.
2. Open the chat UI (`uv run dev` + `cd frontend && npm run dev`) or the CLI
   (`uv run devops-agent investigate "<prompt from the script>"`).
3. Use the prompt printed at the end of `setup`.
4. Record (see below).
5. `teardown`.

### Timing note for CloudTrail cases (M1, H2)
CloudTrail management events can take **5–15 minutes** to show up in Event
history. Run `setup`, wait, *then* investigate so the agent can correlate the
deploy / policy change. The other scenarios are immediate.

### Bonus: event-driven (hands-off) demo
The most impressive GIF is autonomous detection. After enabling event
infrastructure (**Settings → AWS Configuration → Create Infrastructure**), run
`e3_alarm_in_alarm.py setup` or `m1_bad_deploy.py setup` and **don't touch the
chat** — the alarm/event flows EventBridge → SQS → auto-investigation and appears
on the **Monitoring** dashboard with a root cause and confidence. Record that page.

### Make the agent sharper first (optional)
Only the `lambda-throttling` skill ships today. Dropping in extra `SKILL.md` files
(zero code — auto-discovered at startup) visibly improves M3/H1/H2:
`src/skills/ecs-deployment-failure/`, `src/skills/dynamodb-throttling/`,
`src/skills/iam-permission-denied/`. See `docs/skills.md` for the format.

---

## Recording GIFs / short demos

**Recommended pipeline: OBS → trim → convert to GIF (or keep as MP4).**

### 1. Capture with OBS Studio (free, Windows)
- Source: **Display Capture** or **Window Capture** of the browser/terminal.
- Output: record to **MP4** (Settings → Output → Recording). MP4 is easier to
  trim than capturing straight to GIF.
- Crop to just the chat/monitoring panel using a **Crop/Pad filter** so the GIF
  isn't full-screen (smaller file, more focus).
- Bump base canvas to the area you care about; 1280×720 or 1080×~720 is plenty.
- Hide the OBS dock / cursor highlight unless you want a click indicator.

### 2. Trim
- Quick cuts: **LosslessCut** (free) — no re-encode, frame-accurate in/out.
- More editing (zooms, captions, callouts): **DaVinci Resolve** (free), **Clipchamp**
  (ships with Windows), or **ScreenToGif** if you'd rather capture + edit + export
  GIF in one tool.

### 3. Convert MP4 → GIF
GIFs balloon in size fast. Use ffmpeg with a generated palette for crisp,
small output:

```bash
# 1) build an optimized palette
ffmpeg -i demo.mp4 -vf "fps=12,scale=900:-1:flags=lanczos,palettegen" palette.png
# 2) render the gif using it
ffmpeg -i demo.mp4 -i palette.png -lavfi "fps=12,scale=900:-1:flags=lanczos[x];[x][1:v]paletteuse" demo.gif
```

Tips for small, sharp GIFs:
- **fps 10–12** is enough for UI demos (streaming text still reads fine).
- Cap width ~800–1000px; height auto (`-1`).
- Keep clips **≤ 15–20s** — speed up dead air (tool-call waits) in editing rather
  than recording a long pause. For the streaming token effect, 2x speed reads well.
- If GitHub README size matters, prefer an **MP4** (autoplays muted, much smaller)
  or host the GIF and link it.

### Alternative all-in-one tools
- **ScreenToGif** (Windows, free) — record a region, edit frames, export GIF directly.
  Great for short single-window demos; skips OBS+ffmpeg entirely.
- **Terminalizer** / **asciinema + agg** — for crisp *terminal/CLI* demos
  (`uv run devops-agent investigate ...`) rendered as lightweight GIFs.

### What to actually show
- The streaming response + the **collapsible tool-call inspector** expanding to
  reveal which AWS tools ran — that's the differentiator.
- For ⭐ cases, frame the moment the agent states the correlation ("errors began
  at HH:MM, matching the deploy at HH:MM").
- End on the structured **root cause + mitigation** block.
