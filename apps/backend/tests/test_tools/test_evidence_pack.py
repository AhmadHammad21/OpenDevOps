"""Unit tests for the evidence-pack builder, console deeplinks, and the ranked-hypotheses
schema extension to submit_investigation."""

from __future__ import annotations

import inspect

from opendevops_core.agent.evidence import (
    build_evidence_pack,
    console_deeplink,
    exact_command,
)


def test_console_deeplink_log_group_encoding():
    url = console_deeplink("get_log_events", {"log_group": "/aws/lambda/fn"}, "us-east-1")
    assert url == (
        "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1"
        "#logsV2:log-groups/log-group/$252Faws$252Flambda$252Ffn"
    )


def test_console_deeplink_logs_insights_query_detail():
    url = console_deeplink(
        "query_logs_insights",
        {"log_group": "/aws/lambda/fn", "query": "fields @timestamp", "hours": 2},
        "eu-west-1",
    )
    assert url.startswith(
        "https://eu-west-1.console.aws.amazon.com/cloudwatch/home?region=eu-west-1"
        "#logsV2:logs-insights$3FqueryDetail$3D"
    )
    # Relative window encoded as seconds; query string escaped (space -> *20, @ -> *40).
    assert "start~-7200" in url
    assert "editorString~'fields*20*40timestamp" in url
    assert "source~(~'*2faws*2flambda*2ffn)" in url


def test_console_deeplink_none_without_region():
    assert console_deeplink("get_log_events", {"log_group": "/x"}, None) is None


def test_exact_command_only_for_query_and_bash():
    assert exact_command("query_logs_insights", {"query": "stats count(*)"}) == "stats count(*)"
    assert exact_command("run_bash_command", {"command": "az vm list"}) == "az vm list"
    assert exact_command("get_alarms", {"state": "ALARM"}) is None


def _conclusion(hypotheses=None, evidence=None):
    args = {
        "root_cause_category": "RESOURCE_LIMIT",
        "root_cause_summary": "throttled",
        "confidence": "HIGH",
        "evidence": evidence if evidence is not None else ["flat evidence"],
    }
    if hypotheses is not None:
        args["hypotheses"] = hypotheses
    return {"tool_name": "submit_investigation", "args": args, "id": "concl"}


def test_build_pack_links_evidence_to_tool_call():
    tool_calls = [
        {
            "id": "tc-metric",
            "tool_name": "get_metric_data",
            "args": {
                "namespace": "AWS/Lambda",
                "metric": "Throttles",
                "dimensions": [{"Name": "FunctionName", "Value": "payment-fn"}],
            },
            "result": {"count": 1},
        },
        _conclusion(
            hypotheses=[
                {
                    "hypothesis": "concurrency",
                    "evidence": ["payment-fn throttled hard"],
                    "confidence": "HIGH",
                }
            ]
        ),
    ]
    pack = build_evidence_pack("s1", "us-east-1", tool_calls)

    assert pack["has_conclusion"] is True
    assert len(pack["tool_calls"]) == 1  # conclusion excluded from replay
    linked = pack["hypotheses"][0]["evidence"][0]["tool_call_id"]
    assert linked == "tc-metric"


def test_build_pack_falls_back_to_flat_evidence_for_legacy():
    """Old investigations without `hypotheses` still produce one grouped hypothesis."""
    pack = build_evidence_pack("s2", "us-east-1", [_conclusion(evidence=["only flat"])])
    assert len(pack["hypotheses"]) == 1
    assert pack["hypotheses"][0]["evidence"][0]["text"] == "only flat"
    assert pack["hypotheses"][0]["confidence"] == "HIGH"


def test_build_pack_no_conclusion():
    pack = build_evidence_pack("s3", "us-east-1", [])
    assert pack["has_conclusion"] is False
    assert pack["hypotheses"] == []


def test_submit_investigation_has_hypotheses_param():
    from opendevops_core.tools.final_answer import submit_investigation

    sig = inspect.signature(submit_investigation)
    assert "hypotheses" in sig.parameters
    # Must stay a primitive list type so DeepAgents can infer the schema.
    assert sig.parameters["hypotheses"].annotation == list[dict]
