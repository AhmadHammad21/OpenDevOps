# Benchmark

Reproducible results for the OpenDevOps investigation agent on the bundled
incident benchmark. Every number here is regenerable with `make eval` (see
[`eval.md`](./eval.md) for the harness). This page is the "show me it works"
artifact — for engineers evaluating the tool and for sharing the headline
numbers.

> **Reproducibility is the point.** These aren't cherry-picked transcripts.
> Each scenario stands up a real broken AWS/Azure resource, the agent
> investigates over the same `/chat` API a user hits, and the answer is scored
> against ground truth. Re-run it yourself and you should land within noise of
> these figures.

---

## Headline KPIs

Latest sweep — **2026-06-02**, model `openrouter/openai/gpt-oss-120b` (a
commodity open-weight model, deliberately *not* a frontier model):

| Metric | Result |
|---|---|
| **Root-cause accuracy** | **9 / 10 (90%)** |
| **Median time to root cause** | **~52 s** |
| Total time, 10 incidents | ~9 min (541.6 s) |
| **Cost per investigation** | **~$0.03** (≈$0.25–0.40 for all 10)¹ |
| Tool calls per investigation | ~9 |
| Cloud APIs touched | CloudWatch, CloudTrail, Lambda, ECS, IAM, EC2, Azure VM |

¹ In-app token accounting is being calibrated (it currently under-counts
reasoning tokens — tracked in issue #59). The cost figures here use the
**OpenRouter dashboard actuals** as the source of truth, expressed as a range.

**The story in one line:** *even on a cheap open model, the agent finds the
true root cause of 9 out of 10 real incidents in under a minute each, for a few
cents.*

---

## Why these three KPIs

| KPI | Who it's for | Why it matters |
|---|---|---|
| **Accuracy (9/10)** | Engineers | Trust. A faster wrong answer is worthless on call. 90% on a commodity model — frontier models score higher (see below). |
| **Time to root cause (~52 s)** | Engineers / SRE leads | MTTR. The agent correlates alarms, logs, metrics and CloudTrail in ~1 min — work that takes an on-call engineer tens of minutes of manual digging. |
| **Cost per investigation (~$0.03)** | Buyers / investors | Unit economics. The marginal cost of an investigation is cents, and it's model-portable — it drops as open models get cheaper. |

---

## Full results

| # | Scenario | Result | Latency | Tools | Root cause found |
|---|---|---|---|---|---|
| 001 | Lambda crashing (`KeyError`) | ✅ PASS | 50.9 s | 9 | SYSTEM_CHANGE |
| 002 | Lambda throttled (concurrency) | ✅ PASS | 53.1 s | 12 | RESOURCE_LIMIT |
| 003 | Azure VM deallocated | ✅ PASS | 52.1 s | 9 | SYSTEM_CHANGE |
| 004 | CloudWatch alarm → failing Lambda | ✅ PASS | ~52 s | ~10 | COMPONENT_FAILURE |
| 005 | Lambda → DynamoDB throttle | ✅ PASS | 100.9 s | 12 | RESOURCE_LIMIT |
| 006 | IAM permission regression | ✅ PASS | 23.7 s | 5 | SYSTEM_CHANGE |
| 007 | Lambda VPC no egress | ❌ FAIL | 62.0 s | 10 | (mis-categorized²) |
| 008 | Bad deploy (`JSONDecodeError`) | ✅ PASS | 42.2 s | 6 | SYSTEM_CHANGE |
| 009 | Lambda timeout misconfig | ✅ PASS | 64.1 s | 9 | RESOURCE_LIMIT |
| 010 | ECS image pull failure | ✅ PASS | 41.1 s | 9 | SYSTEM_CHANGE |

² **The one honest miss.** On the VPC-no-egress incident the agent's *narrative*
was correct ("Lambda runs in a VPC without a NAT gateway, lacks outbound
connectivity") but it labeled the category `RESOURCE_LIMIT` instead of a
routing/dependency cause — contradicting its own evidence. We deliberately do
**not** loosen the scorer to accept it; a benchmark that excuses its model's
mistakes is worthless. Frontier models (e.g. Claude Sonnet, Gemini 2.5) classify
this one correctly.

---

## Cost & speed comparison

> ⚠️ **Verify the competitor rate before quoting this externally.** The
> per-second figure below is an assumption, not a sourced number — confirm it
> against the vendor's published pricing before putting it in front of
> customers or investors.

Framing: *if a per-second-billed managed agent took the same wall-clock time to
work these 10 incidents, what would it cost vs OpenDevOps?*

| | Time (10 incidents) | Cost | Per incident |
|---|---|---|---|
| Per-second managed agent @ ~$0.008/s *(assumed)* | 541.6 s | **~$4.33** | ~$0.43 |
| **OpenDevOps** (gpt-oss-120b via OpenRouter) | 541.6 s | **~$0.25–0.40** | **~$0.03** |
| | | **≈ 10–15× cheaper** | |

This is a like-for-like *wall-clock* comparison; it assumes the competitor
takes the same time, which should itself be measured rather than assumed. The
durable point isn't the exact multiple — it's the **structural** one: OpenDevOps'
marginal cost is the LLM token bill, which is a few cents on commodity models
and keeps falling, with no per-seat or per-second platform tax.

---

## ROI: what one investigation actually replaces

> Assumptions are explicit and conservative — adjust the engineer rate to your
> own loaded cost. These are illustrative unit economics, not measured in this
> benchmark.

The real comparison isn't agent-vs-agent — it's **agent-vs-an-engineer doing it
by hand**. Working one of these incidents manually means an on-call engineer
pulling CloudWatch alarms, log groups, metric graphs, and CloudTrail, then
correlating them.

| | Per incident |
|---|---|
| Manual triage by an engineer (20–40 min @ ~$100/hr loaded) | **~$33–67** |
| OpenDevOps investigation (~52 s, gpt-oss-120b) | **~$0.03** |
| **Return on the LLM spend** | **~1,000–2,000×** |

Put differently: the agent replaces ~$50 of skilled engineer time with ~3 cents
of compute — and returns the answer in under a minute instead of half an hour.

### Monthly run-rate at scale

A team handling **500 incidents/month**:

| | Monthly cost |
|---|---|
| Engineer triage time (500 × ~$50) | **~$25,000** |
| Per-second managed agent (500 × ~$0.43) | **~$215** |
| **OpenDevOps** (500 × ~$0.03) | **~$15** |

The headline isn't "$15 vs $215" — it's that **$15 of compute deflects ~$25,000
of toil**, and that ratio holds (or improves) as open-model prices fall.

---

## Model portability (the real moat)

The harness scores any model behind the same `/chat` API — swap the model in
**Settings → Agent config → LLM** and re-run. Observed pattern:

- **Frontier models** (Claude Sonnet/Opus, Gemini 2.5 Pro) — highest accuracy,
  reliable tool-calling. Use for production where being right matters most.
- **Mid-tier / open models** (gpt-oss-120b, Gemini 2.5 Flash) — ~8–9/10 at a
  fraction of the cost. Strong default for cost-sensitive deployments.
- **Small models** (sub-70B, budget tiers) — fall off, mostly by failing to
  emit a structured conclusion rather than by reasoning errors.

You are never locked to one vendor's model or price. As open models improve,
the same agent gets better and cheaper for free.

---

## Caveats (read these before quoting numbers)

1. **Cost accuracy.** In-app token accounting under-counts reasoning tokens for
   some providers (issue #59). Treat the OpenRouter/Anthropic dashboard as the
   billing source of truth until that's reconciled.
2. **Competitor pricing is unverified** — see the warning above.
3. **MTTR vs humans is illustrative**, not measured here. The ~52 s is the
   agent's; the "tens of minutes" human baseline is an industry-typical range,
   not a controlled A/B in this benchmark.
4. **Sample size is 10 scenarios.** Enough to catch regressions and set a
   directional headline; not a statistical claim. Expanding the suite is
   ongoing.
5. **Numbers are model- and time-stamped.** Re-running on a different model or
   date will move them — that's the intended use, not a bug.

---

## Reproduce it

```bash
# one full sweep (real cloud + real LLM cost — see eval.md cost guard)
make eval                                  # or:
uv run python demos/eval/run.py --setup-profile default
```

Results land in `demos/eval/results/<timestamp>/report.md` (+ `results.json`
for dashboards). Re-run on your own model to generate your own row in the
portability table above.
