"""Generate apps/documentation/tool_inventory.md from the live introspected inventory.

This page is generated, never hand-edited — it is sourced from the same
``build_inventory()`` introspection that backs the ``/api/inventory`` endpoint, so the
docs and the runtime can never disagree. Regenerate after changing tools, the bash
allowlist, or the AWS permission probes:

    cd apps/backend && uv run python scripts/gen_tool_inventory.py
"""

from __future__ import annotations

from pathlib import Path

from opendevops_core.agent.inventory import build_inventory

_OUT = Path(__file__).resolve().parents[2] / "documentation" / "tool_inventory.md"


def _param_cell(p: dict) -> str:
    req = "required" if p["required"] else f"`{p['default']!r}`"
    type_str = p["type"].replace("|", "\\|")  # don't break the markdown table
    return f"| `{p['name']}` | `{type_str}` | {req} |"


def _render(inv: dict) -> str:
    out: list[str] = []
    out.append("# Tool & Permission Inventory")
    out.append("")
    out.append(
        "> **Generated file — do not edit by hand.** Produced by "
        "`apps/backend/scripts/gen_tool_inventory.py` from the live code "
        "(`opendevops_core.agent.inventory.build_inventory`), the same source that backs "
        "the read-only `GET /api/inventory` endpoint. Regenerate with "
        "`cd apps/backend && uv run python scripts/gen_tool_inventory.py`."
    )
    out.append("")
    out.append(
        "This is the trust artifact: exactly what the agent can inspect — every registered "
        "tool and its parameters, the read-only bash command allowlist, the AWS "
        "read-permission probe, and the per-cloud capability tiers. Everything is read-only."
    )
    out.append("")

    out.append("## Capability by cloud")
    out.append("")
    out.append(
        "| Cloud | Structured SDK tools | CLI access (`bash` tool) | Event-driven + polling |"
    )
    out.append("|---|---|---|---|")
    for p in inv["providers"]:
        active = " (active)" if p["active"] else ""
        out.append(
            f"| **{p['name'].upper()}**{active} | {p['structured_tools']} | "
            f"{'yes' if p['cli_access'] else 'no'} | "
            f"{'yes' if p['event_driven_and_polling'] else 'no'} |"
        )
    out.append("")
    out.append(
        f"Active provider: **{inv['active_provider']}** · "
        f"total registered tools: **{inv['tool_count']}**."
    )
    out.append("")

    out.append("## Registered tools")
    out.append("")
    # Group by module for readability, preserving registration order within a group.
    seen: list[str] = []
    by_mod: dict[str, list[dict]] = {}
    for t in inv["tools"]:
        mod = t["module"].split(".")[-1]
        if mod not in by_mod:
            by_mod[mod] = []
            seen.append(mod)
        by_mod[mod].append(t)
    for mod in seen:
        out.append(f"### `{mod}`")
        out.append("")
        for t in by_mod[mod]:
            out.append(f"#### `{t['name']}` → `{t['returns']}`")
            out.append("")
            if t["description"]:
                out.append(t["description"])
                out.append("")
            if t["parameters"]:
                out.append("| Param | Type | Default |")
                out.append("|---|---|---|")
                for p in t["parameters"]:
                    out.append(_param_cell(p))
            else:
                out.append("*No parameters.*")
            out.append("")

    out.append("## Bash command allowlist")
    out.append("")
    bash = inv["bash_allowlist"]
    out.append(
        f"`run_bash_command` runs only read-only commands, validated against this allowlist "
        f"before execution. Shell chaining is **{bash['shell_chaining']}**, `shell=True` is "
        f"never used, output is capped at {bash['max_output_chars']} chars, and every command "
        f"has a hard {bash['timeout_seconds']}s timeout."
    )
    out.append("")

    def _verbs(items: list[str]) -> str:
        return ", ".join("`" + v + "`" for v in items) or "none"

    aws = bash["aws"]
    out.append(
        f"- **aws** — {aws['note']}. Read-only verbs: {_verbs(aws['readonly_verbs'])}. "
        f"Blocked global flags: {_verbs(aws['blocked_global_flags'])}."
    )
    out.append(
        f"- **az** — {bash['az']['note']}. Read-only verbs: {_verbs(bash['az']['readonly_verbs'])}."
    )
    out.append(f"- **kubectl** — subcommands: {_verbs(bash['kubectl']['subcommands'])}.")
    out.append(f"- **docker** — subcommands: {_verbs(bash['docker']['subcommands'])}.")
    out.append("")

    out.append("## AWS read-permission matrix")
    out.append("")
    out.append(
        "One lightweight read call per service verifies the agent's credentials "
        "(surfaced by the in-app permission checker)."
    )
    out.append("")
    out.append("| Service | boto3 client | Read operation |")
    out.append("|---|---|---|")
    for r in inv["aws_permission_matrix"]:
        out.append(f"| {r['service']} | `{r['boto3_service']}` | `{r['operation']}` |")
    out.append("")
    return "\n".join(out)


def main() -> None:
    inv = build_inventory()
    _OUT.write_text(_render(inv), encoding="utf-8")
    print(f"Wrote {_OUT} ({inv['tool_count']} tools)")


if __name__ == "__main__":
    main()
