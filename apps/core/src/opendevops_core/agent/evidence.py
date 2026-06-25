"""Read-side evidence-pack builder.

Turns the verbatim tool-call rows already persisted for a session into a replayable
evidence pack: hypotheses grouped from the investigation conclusion, each evidence
item tied back to the tool call that produced it, the exact query/command that ran,
and a deterministic cloud-console deeplink where one applies.

This is pure presentation logic — it reads existing data only and never mutates state.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

# Characters the AWS console leaves un-escaped inside its hash-object string tokens.
_CONSOLE_SAFE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._")

# Map a tool name to the AWS service it belongs to, for grouping/labels.
_SERVICE_BY_TOOL: dict[str, str] = {
    "get_alarms": "CloudWatch",
    "get_alarm_history": "CloudWatch",
    "get_metric_data": "CloudWatch",
    "get_log_events": "CloudWatch Logs",
    "describe_log_groups": "CloudWatch Logs",
    "query_logs_insights": "CloudWatch Logs",
    "lookup_cloudtrail_events": "CloudTrail",
    "list_ecs_clusters": "ECS",
    "list_ecs_services": "ECS",
    "describe_ecs_service": "ECS",
    "get_ecs_task_logs": "ECS",
    "list_lambda_functions": "Lambda",
    "get_lambda_function_config": "Lambda",
    "get_lambda_error_rate": "Lambda",
    "describe_ec2_instances": "EC2",
    "get_ec2_system_status": "EC2",
    "describe_rds_instances": "RDS",
    "get_rds_events": "RDS",
    "get_caller_identity": "IAM",
    "get_iam_role_policies": "IAM",
    "run_bash_command": "CLI",
}


def _console_quote(value: str) -> str:
    """Encode a path segment for the CloudWatch console hash (e.g. a log-group name).

    The console double-encodes: standard percent-encoding, then `%` itself becomes `$25`.
    `/aws/lambda/fn` -> `$252Faws$252Flambda$252Ffn`.
    """
    return urllib.parse.quote(value, safe="").replace("%", "$25")


def _console_str(value: str) -> str:
    """Serialize a string into an AWS console hash-object token (`'` prefix, `*xx` escapes)."""
    out = ["'"]
    for ch in value:
        if ch in _CONSOLE_SAFE:
            out.append(ch)
        else:
            out.extend(f"*{b:02x}" for b in ch.encode("utf-8"))
    return "".join(out)


def _console_obj(obj: Any) -> str:
    """Serialize a python value to the AWS console hash-object format used in deeplinks."""
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, str):
        return _console_str(obj)
    if isinstance(obj, dict):
        # Objects carry a leading tilde; pairs are `key~value` joined by `~`.
        return "~(" + "~".join(f"{k}~{_console_obj(v)}" for k, v in obj.items()) + ")"
    if isinstance(obj, (list, tuple)):
        # Arrays have no leading tilde of their own — each element is tilde-prefixed.
        return "(" + "".join(f"~{_console_obj(v)}" for v in obj) + ")"
    return "null"


def _cw_base(region: str) -> str:
    return f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#"


def console_deeplink(tool_name: str, args: dict, region: str | None) -> str | None:
    """Build a deterministic AWS-console deeplink from a tool call's stored args.

    Returns None when the tool has no meaningful console target (or no region). Azure /
    bash calls have no deeplink — their replay value is the literal command string.
    """
    if not region or not isinstance(args, dict):
        return None

    if tool_name in ("get_log_events", "describe_log_groups"):
        lg = args.get("log_group") or args.get("prefix")
        if not lg:
            return f"{_cw_base(region)}logsV2:log-groups"
        return f"{_cw_base(region)}logsV2:log-groups/log-group/{_console_quote(lg)}"

    if tool_name == "query_logs_insights":
        lg = args.get("log_group")
        query = args.get("query", "")
        hours = args.get("hours", 1)
        try:
            start = -int(hours) * 3600
        except (TypeError, ValueError):
            start = -3600
        detail = {
            "end": 0,
            "start": start,
            "timeType": "RELATIVE",
            "unit": "seconds",
            "editorString": query,
            "isLiveTail": False,
            "source": [lg] if lg else [],
        }
        return f"{_cw_base(region)}logsV2:logs-insights$3FqueryDetail$3D" + _console_obj(detail)

    if tool_name in ("get_alarms", "get_alarm_history"):
        name = args.get("alarm_name")
        if name:
            return f"{_cw_base(region)}alarmsV2:alarm/{_console_quote(name)}"
        return f"{_cw_base(region)}alarmsV2:"

    if tool_name == "get_metric_data":
        namespace = args.get("namespace", "")
        metric = args.get("metric", "")
        dims = args.get("dimensions") or []
        series: list[Any] = [namespace, metric]
        for d in dims:
            if isinstance(d, dict) and "Name" in d and "Value" in d:
                series.extend([d["Name"], d["Value"]])
        graph = {"metrics": [series], "region": region}
        return f"{_cw_base(region)}metricsV2:graph={_console_obj(graph)}"

    if tool_name in ("get_lambda_function_config", "get_lambda_error_rate"):
        name = args.get("name")
        if name:
            enc = urllib.parse.quote(name, safe="")
            return f"https://{region}.console.aws.amazon.com/lambda/home?region={region}#/functions/{enc}"

    if tool_name == "get_ec2_system_status":
        iid = args.get("instance_id")
        if iid:
            return (
                f"https://{region}.console.aws.amazon.com/ec2/home?region={region}"
                f"#InstanceDetails:instanceId={urllib.parse.quote(iid, safe='')}"
            )

    if tool_name == "get_rds_events":
        dbid = args.get("db_identifier")
        if dbid:
            return (
                f"https://{region}.console.aws.amazon.com/rds/home?region={region}"
                f"#database:id={urllib.parse.quote(dbid, safe='')};is-cluster=false"
            )

    return None


def exact_command(tool_name: str, args: dict) -> str | None:
    """The verbatim query/command a tool ran, when it stored one (Logs Insights, CLI)."""
    if not isinstance(args, dict):
        return None
    if tool_name == "query_logs_insights":
        return args.get("query")
    if tool_name == "run_bash_command":
        return args.get("command")
    return None


def _identifiers(args: dict) -> list[str]:
    """Distinctive string values from a tool call's args, used to link evidence text."""
    ids: list[str] = []
    if not isinstance(args, dict):
        return ids
    for value in args.values():
        if isinstance(value, str) and len(value) >= 4:
            ids.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    v = item.get("Value")
                    if isinstance(v, str) and len(v) >= 4:
                        ids.append(v)
    return ids


def _replay_entry(index: int, tc: dict, region: str | None) -> dict:
    tool_name = tc.get("tool_name", "")
    args = tc.get("args") or {}
    return {
        "id": tc.get("id") or f"tc-{index}",
        "index": index,
        "tool": tool_name,
        "service": _SERVICE_BY_TOOL.get(tool_name, "Other"),
        "args": args,
        "result": tc.get("result"),
        "error": tc.get("error"),
        "command": exact_command(tool_name, args),
        "console_url": console_deeplink(tool_name, args, region),
        "created_at": tc.get("created_at"),
    }


def _match_tool_call(evidence_text: str, replay: list[dict]) -> str | None:
    """Best-effort, deterministic link from an evidence string to the tool call id
    that most likely produced it — by counting how many of the call's distinctive
    arg identifiers appear in the evidence text."""
    if not evidence_text:
        return None
    text = evidence_text.lower()
    best_id: str | None = None
    best_score = 0
    for entry in replay:
        score = sum(1 for ident in _identifiers(entry["args"]) if ident.lower() in text)
        # A bare mention of the tool name is a weak signal, used only as a tie-breaker.
        if entry["tool"] and entry["tool"].lower() in text:
            score += 1
        if score > best_score:
            best_score = score
            best_id = entry["id"]
    return best_id if best_score > 0 else None


def build_evidence_pack(
    session_id: str,
    aws_region: str | None,
    tool_calls: list[dict],
) -> dict:
    """Assemble the replayable evidence pack for a session.

    `tool_calls` are the raw persisted rows (tool_name, args, result, error, id, created_at),
    ordered oldest-first. The latest `submit_investigation` row is the conclusion; the rest
    are the supporting calls that get replayed and linked to each hypothesis's evidence.
    """
    conclusion: dict | None = None
    supporting: list[dict] = []
    for tc in tool_calls:
        if tc.get("tool_name") == "submit_investigation":
            conclusion = tc.get("args") or {}
        else:
            supporting.append(tc)

    replay = [_replay_entry(i, tc, aws_region) for i, tc in enumerate(supporting)]

    # Prefer the ranked hypotheses (new schema); fall back to the legacy single
    # root-cause + flat evidence so older investigations still render.
    raw_hypotheses: list[dict] = []
    if conclusion:
        hyps = conclusion.get("hypotheses")
        if isinstance(hyps, list) and hyps:
            raw_hypotheses = [h for h in hyps if isinstance(h, dict)]
        else:
            raw_hypotheses = [
                {
                    "hypothesis": conclusion.get("root_cause_summary", ""),
                    "evidence": conclusion.get("evidence", []),
                    "confidence": conclusion.get("confidence", "LOW"),
                }
            ]

    hypotheses: list[dict] = []
    for h in raw_hypotheses:
        ev_items = []
        for ev in h.get("evidence", []) or []:
            if not isinstance(ev, str):
                continue
            ev_items.append({"text": ev, "tool_call_id": _match_tool_call(ev, replay)})
        hypotheses.append(
            {
                "hypothesis": h.get("hypothesis", ""),
                "confidence": h.get("confidence", "LOW"),
                "evidence": ev_items,
            }
        )

    return {
        "session_id": session_id,
        "aws_region": aws_region,
        "has_conclusion": conclusion is not None,
        "root_cause_category": (conclusion or {}).get("root_cause_category"),
        "root_cause_summary": (conclusion or {}).get("root_cause_summary", ""),
        "confidence": (conclusion or {}).get("confidence"),
        "hypotheses": hypotheses,
        "tool_calls": replay,
    }
