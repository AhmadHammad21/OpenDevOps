"""
E3 — CloudWatch alarm in ALARM state, backed by a real failing Lambda.

Deploys an order-processing Lambda that fails on every invocation (a regressed
pricing helper returns None, so the charge math raises a TypeError), invokes it
so real errors + tracebacks land in CloudWatch Logs, and points the
`opendevops-demo-high-errors` alarm at that function's AWS/Lambda Errors metric.
The alarm is then forced into ALARM with set_alarm_state so it shows ALARM
immediately (deterministic, no waiting on CloudWatch evaluation lag) — but the
underlying cause is genuine and discoverable.

This is the only scenario whose prompt names just the *alarm*, not the resource,
so it tests alarm-first triage: alarm -> discover the function -> read logs ->
root cause.

Ask the agent:  "the opendevops-demo-high-errors alarm is firing, what's going on?"
Expect: get_alarms -> find the function -> get_log_events showing the TypeError.

  uv run python demos/aws/e3_alarm_in_alarm.py setup
  uv run python demos/aws/e3_alarm_in_alarm.py teardown
"""

from __future__ import annotations

import _common as c

ALARM = f"{c.PREFIX}-high-errors"
FN = f"{c.PREFIX}-orders"
ROLE = f"{c.PREFIX}-orders-role"
BASIC = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

CODE = """
def get_unit_price(sku):
    # Pricing lookup regressed: returns None for every SKU instead of a number.
    return None

def handler(event, context):
    qty = event.get("quantity", 3)
    price = get_unit_price(event.get("sku", "SKU-1"))
    total = qty * price          # TypeError: can't multiply int by None (price regressed)
    return {"order_total": total}
"""


def setup() -> None:
    sess = c.session()
    c.whoami(sess)

    role = c.ensure_role(sess, ROLE, [BASIC])
    c.create_lambda(sess, FN, CODE, role)
    c.invoke_n(sess, FN, n=10)

    cw = sess.client("cloudwatch")
    cw.put_metric_alarm(
        AlarmName=ALARM,
        AlarmDescription="OpenDevOps demo: order processing error count too high",
        Namespace="AWS/Lambda",
        MetricName="Errors",
        Dimensions=[{"Name": "FunctionName", "Value": FN}],
        Statistic="Sum",
        Period=60,
        EvaluationPeriods=1,
        Threshold=1.0,
        ComparisonOperator="GreaterThanThreshold",
        TreatMissingData="notBreaching",
    )
    # Force ALARM so the demo is instant + deterministic; the real errors are
    # already in Logs/metrics for the agent to find.
    cw.set_alarm_state(
        AlarmName=ALARM,
        StateValue="ALARM",
        StateReason=f"Threshold Crossed: {FN} Errors Sum (10) > 1 over 1 datapoint.",
    )
    c.log("alarm forced into ALARM state")
    c.log("DONE. Investigate: 'the opendevops-demo-high-errors alarm is firing'")


def teardown() -> None:
    sess = c.session()
    try:
        sess.client("cloudwatch").delete_alarms(AlarmNames=[ALARM])
        c.log(f"deleted alarm {ALARM}")
    except Exception as e:  # noqa: BLE001
        c.log(f"alarm delete skipped: {e}")
    c.delete_lambda(sess, FN)
    c.delete_role(sess, ROLE)


if __name__ == "__main__":
    action = c.parse_action(__doc__)
    setup() if action == "setup" else teardown()
