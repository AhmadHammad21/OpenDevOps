#!/usr/bin/env python
"""OpenDevOps Eval runner.

Discovers scenarios under ``demos/eval/scenarios/``, runs each one end-to-end
against a live agent (``/chat`` SSE), scores the answer against ground truth,
and emits a markdown report.

This is **integration** code — it hits real AWS / Azure and pays real LLM
costs. Don't put it in pytest.

  python demos/eval/run.py                       # all scenarios, real /chat + real cloud
  python demos/eval/run.py --scenario 001        # by id prefix
  python demos/eval/run.py --skip-setup          # use already-up infra (fast iter)
  python demos/eval/run.py --skip-teardown
  python demos/eval/run.py --base-url http://localhost:8000
  python demos/eval/run.py --token <jwt>         # auth-required deployments
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from scoring import ScenarioResult, score

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = EVAL_DIR / "scenarios"
RESULTS_DIR = EVAL_DIR / "results"


def _load_env_files() -> None:
    """Read AWS / Azure / LLM credentials from the project's .env files into
    ``os.environ`` so the demo subprocesses we shell out to inherit them.

    Order (first wins for any given key, then existing shell env beats both):
      1. existing process env (highest)
      2. apps/backend/.env  (where AWS_PROFILE / AWS_ACCESS_KEY_ID typically live)
      3. <repo-root>/.env   (optional fallback)

    No python-dotenv dep — parser is intentionally simple: KEY=VALUE per line,
    blank/comment lines ignored, surrounding quotes stripped. Good enough for
    standard .env files; doesn't try to handle multi-line values or expansion.
    """
    for path in (REPO_ROOT / "apps" / "backend" / ".env", REPO_ROOT / ".env"):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _load_scenarios(filter_id: str | None) -> list[dict[str, Any]]:
    """Discover scenario.json files; return a list sorted by directory name."""
    out: list[dict[str, Any]] = []
    if not SCENARIOS_DIR.exists():
        return out
    for d in sorted(SCENARIOS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if filter_id and not d.name.startswith(filter_id):
            continue
        cfg_path = d / "scenario.json"
        if not cfg_path.exists():
            continue
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["__id__"] = d.name
        cfg["__path__"] = str(d)
        out.append(cfg)
    return out


_run_log_dir: Path | None = None  # set by main(); per-run subprocess log directory
_setup_aws_profile: str | None = None  # set by main(); write-capable profile for setup/teardown


def _run_demo(demo_rel: str, action: str) -> int:
    """Shell out to a demo's setup/teardown. Returns subprocess exit code.

    On failure we print up to ~2000 chars of stderr to the terminal AND persist
    the full stdout+stderr to ``demos/eval/results/<run-id>/<demo>_<action>.log``
    so the actual cloud-provider error is never lost to terminal truncation.

    If ``--setup-profile`` was passed, AWS env vars (KEY_ID / SECRET / PROFILE)
    are rewritten so the subprocess uses that profile via ~/.aws/credentials.
    The runner's own boto3 calls (and the agent server) are not affected.
    """
    script = REPO_ROOT / demo_rel
    if not script.exists():
        print(f"  ! demo script missing: {script}", file=sys.stderr)
        return 1
    print(f"  -> {action}: {demo_rel}")

    sub_env = os.environ.copy()
    if _setup_aws_profile:
        # boto3 prefers explicit env keys over AWS_PROFILE — strip them so the
        # profile actually takes effect. The user's read-only key stays in the
        # parent process for the agent /chat call.
        sub_env["AWS_PROFILE"] = _setup_aws_profile
        for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
            sub_env.pop(k, None)

    proc = subprocess.run(
        [sys.executable, script.name, action],
        cwd=script.parent,
        capture_output=True,
        text=True,
        env=sub_env,
    )
    # Always persist the full output; cloud errors (esp. IAM AccessDenied) are
    # the single most useful thing to inspect when a scenario fails to set up.
    if _run_log_dir is not None:
        slug = Path(demo_rel).stem
        log_path = _run_log_dir / f"{slug}_{action}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"exit={proc.returncode}\n\n--- stdout ---\n{proc.stdout}\n\n--- stderr ---\n{proc.stderr}",
            encoding="utf-8",
        )
    if proc.returncode != 0:
        # Stderr first (where boto3 / az errors land), then truncate generously.
        err = (proc.stderr or proc.stdout or "").strip()
        if len(err) > 2000:
            err = err[:2000] + f"\n    ... [{len(err) - 2000} more chars in log file]"
        print(f"    stderr:\n{err}")
        if _run_log_dir is not None:
            print(f"    full output: {log_path}")
    return proc.returncode


def _post_chat(
    base_url: str,
    token: str | None,
    prompt: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """POST /chat, consume the SSE stream, return collected metrics + the
    submit_investigation tool call args. Synchronous urllib — no extra deps."""
    session_id = str(uuid.uuid4())
    body = json.dumps({"session_id": session_id, "message": prompt}).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        url=f"{base_url.rstrip('/')}/chat",
        data=body,
        method="POST",
        headers=headers,
    )

    tools_called: list[str] = []
    submit_args: dict[str, Any] = {}
    usage: dict[str, Any] = {}
    started = time.time()

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds + 10) as resp:
            buf = b""
            for chunk in resp:
                if time.time() - started > timeout_seconds:
                    return {
                        "error": f"agent did not finish within {timeout_seconds}s",
                        "session_id": session_id,
                    }
                buf += chunk
                while b"\n\n" in buf:
                    raw, buf = buf.split(b"\n\n", 1)
                    for line in raw.splitlines():
                        if not line.startswith(b"data: "):
                            continue
                        try:
                            evt = json.loads(line[6:].decode("utf-8"))
                        except json.JSONDecodeError:
                            continue
                        if evt.get("type") == "tool_call":
                            tools_called.append(evt.get("tool", ""))
                            if evt.get("tool") == "submit_investigation":
                                submit_args = evt.get("args") or {}
                        elif evt.get("type") == "done":
                            usage = evt.get("usage") or {}
                            return {
                                "session_id": session_id,
                                "tools_called": tools_called,
                                "submit_args": submit_args,
                                "latency_ms": usage.get("latency_ms", 0),
                                "input_tokens": usage.get("input_tokens", 0),
                                "output_tokens": usage.get("output_tokens", 0),
                                "cost_usd": usage.get("cost_usd"),
                                "model": usage.get("model", ""),
                            }
                        elif evt.get("type") == "error":
                            return {
                                "error": evt.get("message") or "agent error",
                                "session_id": session_id,
                                "tools_called": tools_called,
                            }
    except urllib.error.URLError as e:
        return {"error": f"network error: {e}", "session_id": session_id}

    return {"error": "stream ended without 'done' event", "session_id": session_id}


def run_one(
    scenario: dict[str, Any],
    args: argparse.Namespace,
) -> ScenarioResult:
    sid = scenario["__id__"]
    print(f"\n== {sid} — {scenario.get('name', '(no name)')}")

    setup_rc = 0 if args.skip_setup else _run_demo(scenario["demo"], "setup")
    if setup_rc != 0:
        # Setup may have created PARTIAL state before failing (e.g. IAM role
        # succeeded, Lambda creation failed). Always try teardown so we don't
        # leak orphan resources. Demo teardowns are idempotent — safe to call
        # even if setup never created anything.
        if not args.skip_teardown:
            print("  ! setup failed — running teardown to clean any partial state")
            _run_demo(scenario["demo"], "teardown")
        return _failure(sid, f"setup exited with code {setup_rc}")

    # CloudWatch / Lambda often takes ~30s to start showing metrics. Give it
    # time so the agent sees the broken state instead of an empty graph.
    if not args.skip_setup:
        propagation = scenario.get("propagation_seconds", 30)
        print(f"  . waiting {propagation}s for cloud state to propagate")
        time.sleep(propagation)

    print(f"  -> /chat: {scenario['prompt']!r}")
    chat_result = _post_chat(
        args.base_url,
        args.token,
        scenario["prompt"],
        timeout_seconds=scenario.get("timeout_seconds", 180),
    )

    if not args.skip_teardown:
        # Always teardown, even on chat failure — don't leak resources.
        _run_demo(scenario["demo"], "teardown")

    if "error" in chat_result:
        return _failure(sid, chat_result["error"], partial=chat_result)

    return score(
        scenario_id=sid,
        agent_output=chat_result.get("submit_args") or {},
        ground_truth=scenario.get("ground_truth") or {},
        metrics={
            "tools_called": chat_result.get("tools_called", []),
            "tool_call_count": len(chat_result.get("tools_called", [])),
            "latency_ms": chat_result.get("latency_ms", 0),
            "input_tokens": chat_result.get("input_tokens", 0),
            "output_tokens": chat_result.get("output_tokens", 0),
            "cost_usd": chat_result.get("cost_usd"),
            "model": chat_result.get("model", ""),
        },
    )


def _failure(sid: str, msg: str, partial: dict[str, Any] | None = None) -> ScenarioResult:
    p = partial or {}
    return ScenarioResult(
        scenario_id=sid,
        passed=False,
        reasons=[msg],
        latency_ms=int(p.get("latency_ms", 0)),
        tool_call_count=len(p.get("tools_called", []) or []),
        cost_usd=p.get("cost_usd"),
        input_tokens=int(p.get("input_tokens", 0)),
        output_tokens=int(p.get("output_tokens", 0)),
        model=p.get("model", ""),
        agent_root_cause_category="",
        agent_root_cause_summary="",
        error=msg,
    )


def _print_table(results: list[ScenarioResult]) -> None:
    """Pretty single-glance summary for the terminal."""
    print("\n" + "-" * 80)
    print(f"{'scenario':<28} {'pass':<5} {'latency':<8} {'tools':<6} {'cost':<10} {'cause':<22}")
    print("-" * 80)
    for r in results:
        pass_mark = "PASS" if r.passed else "FAIL"
        cost = f"${r.cost_usd:.4f}" if r.cost_usd is not None else "—"
        print(
            f"{r.scenario_id:<28} {pass_mark:<5} "
            f"{r.latency_ms/1000:.1f}s   {r.tool_call_count:<6} {cost:<10} "
            f"{r.agent_root_cause_category:<22}"
        )
    print("-" * 80)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    total_cost = sum((r.cost_usd or 0) for r in results)
    print(f"{passed}/{total} passed  . total cost ${total_cost:.4f}")


def _write_report(results: list[ScenarioResult], report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    md = report_dir / "report.md"
    json_path = report_dir / "results.json"

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    total_cost = sum((r.cost_usd or 0) for r in results)
    median_latency = (
        sorted(r.latency_ms for r in results)[len(results) // 2] if results else 0
    )

    lines: list[str] = []
    lines.append(f"# OpenDevOps Eval — {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(
        f"**{passed}/{total} root causes found** . median {median_latency/1000:.1f}s . "
        f"total ${total_cost:.4f}\n"
    )
    lines.append("| scenario | pass | latency | tools | cost | model | root cause |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        cost = f"${r.cost_usd:.4f}" if r.cost_usd is not None else "—"
        lines.append(
            f"| {r.scenario_id} | {'PASS' if r.passed else 'FAIL'} | "
            f"{r.latency_ms/1000:.1f}s | {r.tool_call_count} | {cost} | "
            f"`{r.model}` | {r.agent_root_cause_category or '—'} |"
        )
    lines.append("\n## Per-scenario detail\n")
    for r in results:
        lines.append(f"### {r.scenario_id} — {'PASS' if r.passed else 'FAIL'}")
        if r.agent_root_cause_summary:
            lines.append(f"\n**Agent's root cause:** {r.agent_root_cause_summary}\n")
        for reason in r.reasons:
            lines.append(f"- {reason}")
        if r.error:
            lines.append(f"- **error**: {r.error}")
        lines.append("")
    md.write_text("\n".join(lines), encoding="utf-8")

    json_path.write_text(
        json.dumps([r.__dict__ for r in results], indent=2),
        encoding="utf-8",
    )
    return md


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scenario", help="run only scenarios whose id starts with this")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--token", help="Bearer token for product / auth-enabled deployments")
    p.add_argument("--skip-setup", action="store_true", help="don't run setup.py (use existing state)")
    p.add_argument("--skip-teardown", action="store_true", help="leave broken state up for inspection")
    p.add_argument(
        "--setup-profile",
        help=(
            "AWS profile to use for setup/teardown subprocesses ONLY. "
            "Use a write-capable profile here while keeping the agent on a "
            "read-only one. Example: --setup-profile default"
        ),
    )
    args = p.parse_args()

    # Pull AWS / Azure / etc. creds out of .env so the demo subprocesses inherit
    # them without the user having to remember to `$env:AWS_PROFILE = "..."`.
    _load_env_files()

    scenarios = _load_scenarios(args.scenario)
    if not scenarios:
        print(f"no scenarios matched filter={args.scenario!r}", file=sys.stderr)
        return 1

    # Set up the per-run results dir UP FRONT so _run_demo can write subprocess
    # logs into it as each scenario runs (not only at the end).
    global _run_log_dir, _setup_aws_profile
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RESULTS_DIR / stamp
    _run_log_dir = run_dir
    _setup_aws_profile = args.setup_profile

    print(f"running {len(scenarios)} scenario(s) against {args.base_url}")
    print(f"subprocess logs: {run_dir}")
    if args.setup_profile:
        print(f"setup/teardown will use AWS profile: {args.setup_profile}")
    results: list[ScenarioResult] = []
    for sc in scenarios:
        results.append(run_one(sc, args))

    _print_table(results)

    report_path = _write_report(results, run_dir)
    print(f"\nreport: {report_path}")

    # Exit non-zero if any scenario failed — useful for CI.
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
