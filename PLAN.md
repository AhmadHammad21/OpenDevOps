# PLAN.md — OpenDevOps Agent Roadmap

> An openv-source AWS DevOps Agent clone. Powered by OpenRouter LLMs.
> Investigate incidents, find root causes, ship fixes faster.

---

## Vision

AWS DevOps Agent is great but costs a fortune and locks you into AWS. We're building the
open-source equivalent — a CLI-first agentic tool that any team can run with their own AWS
read-only credentials and their preferred LLM via OpenRouter. Eventually: open it up, build
a community, maybe make AWS nervous enough to call.

---

## Guiding Principles

1. **Read before write** — Phase 1 is 100% read-only. No accidental `terraform apply`.
2. **CLI first, UI later** — Ship a great terminal experience before building dashboards.
3. **Transparent reasoning** — Always show what the agent investigated and why.
4. **Swappable everything** — Models, AWS regions, tool sets. No lock-in.
5. **Honest about confidence** — LOW / MEDIUM / HIGH on every finding.

---

## Phase 1 — Solid Foundation (MVP) 🏗️

**Goal:** A working CLI agent that can investigate a described incident using AWS data.

**Duration estimate:** 1–2 weeks solo

### Deliverables
- `devops-agent investigate "high latency on my API"` works end-to-end
- Covers: CloudWatch, CloudTrail, ECS, Lambda, EC2, RDS
- Read-only IAM policy documented and tested
- Structured root cause output (JSON + Rich terminal report)
- Tests with moto mocks — no real AWS calls needed for CI
- Clean README with 5-minute setup guide

### Success Criteria
- [ ] Can identify a Lambda throttling issue from a description alone
- [ ] Can correlate a CloudTrail deployment event with a CloudWatch alarm spike
- [ ] Runs in under 60 seconds for a typical investigation
- [ ] Zero AWS write permissions required

---

## Phase 2 — Smarter Context & Better Signals 🔍

**Goal:** The agent understands *your* environment, not just individual services.

### Features
- **Application topology mapping** — auto-discover how services connect
  (e.g., API Gateway → Lambda → DynamoDB)
- **Alarm correlation** — group related alarms from the same incident window
- **CloudWatch Logs Insights** — structured log queries, not just raw events
- **Cost anomaly detection** — surface unexpected spend spikes alongside incidents
- **`devops-agent ask` Q&A mode** — freeform questions about your environment
- **Investigation history** — save past investigations to a local SQLite DB
- **`devops-agent report`** — daily ops health summary (alarm states, error rates)

### Dependencies
- `sqlite3` (stdlib) for local history
- CloudWatch Logs Insights API integration

---

## Phase 3 — Integrations & Notifications 🔔

**Goal:** Fit into existing DevOps workflows without friction.

### Features
- **Slack webhook output** — post investigation findings to a channel
- **PagerDuty trigger input** — auto-start investigations from PD alerts
- **GitHub integration** — look up recent deployments from PRs/commits
  (correlate "did a deploy happen before this alarm?")
- **Configuration profiles** — named configs for different AWS accounts/environments
  (`devops-agent --profile production investigate "..."`)
- **Multi-region support** — investigate across regions in one run

### Dependencies
- `httpx` for webhook calls
- GitHub API (PyGithub or raw REST)

---

## Phase 4 — Proactive Prevention 🛡️

**Goal:** Don't just react — identify risks before they become incidents.

### Features
- **Pattern analysis** — analyze investigation history to find recurring root causes
- **Observability gap detection** — "you're missing alarms on X"
- **Alarm tuning recommendations** — thresholds that are too loose or too tight
- **Deployment risk scoring** — before you deploy, assess blast radius
- **Weekly ops digest** — proactive recommendations email/Slack report
- **Learned investigation skills** — agent improves from past investigations
  (few-shot examples stored locally and injected into prompts)

---

## Phase 5 — Web UI & Team Features 🖥️

**Goal:** Make it accessible to non-CLI users and entire teams.

### Features
- **Local web dashboard** — FastAPI backend + React frontend
  - Live investigation view
  - Historical investigations browser
  - Alarm heatmap
- **Shared investigation links** — export investigation as HTML report
- **Team annotations** — add notes to investigations
- **Multi-model comparison** — run same investigation with GPT-4o vs Gemini vs Llama, compare

### Dependencies
- `fastapi` + `uvicorn`
- React frontend (or HTMX for simplicity)

---

## Phase 6 — Extensibility & Open Source Growth 🌍

**Goal:** Let the community extend it.

### Features
- **MCP server support** — connect custom tools via Model Context Protocol
- **Custom skill system** — YAML-defined investigation runbooks
  (e.g., "when you see X alarm, always check Y first")
- **Plugin architecture** — third-party tool connectors (Datadog, New Relic, Splunk)
- **`devops-agent skill add <url>`** — install community skills
- **Hosted skills registry** — GitHub repo of community-contributed investigation skills

---

## Tech Decisions & Rationale

### Python over TypeScript
- boto3 is the gold standard for AWS interaction — Python-first, best docs
- Richer ML/AI ecosystem (if we add local models later)
- Easier for DevOps/SRE folks to contribute — Python is their native language
- TypeScript would make sense for a web-heavy product; this is CLI + AI-heavy

### OpenRouter over direct Anthropic/OpenAI
- One API key, access to 100+ models
- Easy to benchmark: same prompt, different models
- Fallback if a model goes down
- Cost transparency per model
- Migration path to direct providers when we need it

### ReAct (Reason+Act) pattern over simple tool calling
- Agent explains its reasoning before each tool call
- Transparent investigation trail users can follow
- Easier to debug when something goes wrong
- More reliable root cause findings vs. "just call all the tools"

### Read-only IAM first
- Safer to open-source — users aren't scared to give an IAM role
- Builds trust before we add write actions
- Forces us to build great reasoning rather than relying on "just fix it"

---

## Open Source Strategy

### Repository Setup
- License: **Apache 2.0** (permissive, enterprise-friendly, AWS uses it)
- `CONTRIBUTING.md` from day one
- GitHub Discussions enabled
- Issues template for bug reports and feature requests

### Community Growth
- Post on Hacker News on launch ("Show HN: Open-source AWS DevOps Agent")
- r/aws, r/devops, r/sre posts
- Write a blog post: "How I built an AWS DevOps Agent clone in Python"
- DEV.to article series: "Building an AI SRE Agent from scratch"
- Twitter/X threads showing real investigations

### AWS Attraction Strategy
- Build something genuinely useful that AWS users talk about
- Benchmark it publicly against AWS DevOps Agent where possible
- Show it working on real incident scenarios (sanitized)
- If it gets traction — AWS has acquired tools that do less (see: Wickr, Cloud9, CodeWhisperer)
- Worst case: you get a great portfolio piece and SRE skills

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LLM makes up AWS findings | Always ground answers in real tool output; never let model invent data |
| AWS API rate limits during investigation | Add exponential backoff + respect service quotas |
| Credentials accidentally logged | Sanitize all log output; never log boto3 client configs |
| Investigation takes too long | Hard cap at `MAX_TOOL_CALLS`; timeout at `INVESTIGATION_TIMEOUT` |
| Model changes behavior on update | Pin model versions in config; test with eval suite |
| Open source gets ignored | Focus on a killer demo video + one great blog post |

---

## Immediate Next Steps (This Week)

1. `uv init opendevops-agent` — create the project
2. Implement `tools/cloudwatch.py` first (most useful, easiest to mock)
3. Write the system prompt in `agent/prompts.py`
4. Build the bare minimum agent loop in `agent/core.py`
5. Wire up `devops-agent investigate` CLI command
6. Test with a real CloudWatch alarm from your AWS account
7. Record a demo GIF for the README

---

*Let's make AWS nervous.*
