"""
E3 — CloudWatch alarm in ALARM state.

Creates an alarm and forces it into ALARM with a realistic reason via
set-alarm-state (instant + deterministic, ideal for a clean GIF). Also pushes
a couple of breaching custom-metric datapoints so the metric graph isn't empty.

Ask the agent:  "the opendevops-demo-high-errors alarm is firing, what's going on?"
Expect: get_alarms -> get_alarm_history -> get_metric_data.

  uv run python demos/e3_alarm_in_alarm.py setup
  uv run python demos/e3_alarm_in_alarm.py teardown
"""

from __future__ import annotations

import datetime as dt

import _common as c

ALARM = f"{c.PREFIX}-high-errors"
NAMESPACE = "OpenDevOpsDemo"
METRIC = "OrderErrors"


def setup() -> None:
    sess = c.session()
    c.whoami(sess)
    cw = sess.client("cloudwatch")

    now = dt.datetime.now(dt.timezone.utc)
    for i in range(5):
        cw.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    "MetricName": METRIC,
                    "Timestamp": now - dt.timedelta(minutes=5 * i),
                    "Value": 42 + i,
                    "Unit": "Count",
                }
            ],
        )
    c.log("pushed breaching datapoints")

    cw.put_metric_alarm(
        AlarmName=ALARM,
        AlarmDescription="OpenDevOps demo: order error count too high",
        Namespace=NAMESPACE,
        MetricName=METRIC,
        Statistic="Sum",
        Period=300,
        EvaluationPeriods=1,
        Threshold=10.0,
        ComparisonOperator="GreaterThanThreshold",
        TreatMissingData="notBreaching",
    )
    cw.set_alarm_state(
        AlarmName=ALARM,
        StateValue="ALARM",
        StateReason="Threshold Crossed: OrderErrors Sum (46) > 10 over 1 datapoint.",
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


if __name__ == "__main__":
    action = c.parse_action(__doc__)
    setup() if action == "setup" else teardown()
