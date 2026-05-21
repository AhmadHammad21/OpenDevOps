"""
E2 — Lambda crashing with an unhandled exception.

Deploys a function whose handler raises a KeyError, then invokes it so the
error rate spikes and a traceback lands in CloudWatch Logs.

Ask the agent:  "opendevops-demo-crashing has a high error rate, investigate"
Expect: get_lambda_error_rate (errors > 0) + get_log_events showing the traceback.

  uv run python demos/e2_lambda_crashing.py setup
  uv run python demos/e2_lambda_crashing.py teardown
"""

from __future__ import annotations

import _common as c

FN = f"{c.PREFIX}-crashing"
ROLE = f"{c.PREFIX}-basic-role"
BASIC = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

CODE = """
def handler(event, context):
    user = event["user_id"]          # KeyError: payload never has this
    return {"charged": user}
"""


def setup() -> None:
    sess = c.session()
    c.whoami(sess)
    role = c.ensure_role(sess, ROLE, [BASIC])
    c.create_lambda(sess, FN, CODE, role)
    c.invoke_n(sess, FN, n=8)
    c.log("DONE. Investigate: 'opendevops-demo-crashing has a high error rate'")


def teardown() -> None:
    sess = c.session()
    c.delete_lambda(sess, FN)
    c.delete_role(sess, ROLE)


if __name__ == "__main__":
    action = c.parse_action(__doc__)
    setup() if action == "setup" else teardown()
