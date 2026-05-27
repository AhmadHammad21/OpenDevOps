"""
M2 — Timeout misconfiguration.

Deploys a function that takes ~3s with a healthy 10s timeout, runs it cleanly,
then lowers the timeout to 1s (UpdateFunctionConfiguration) so every invocation
now dies with "Task timed out after 1.00 seconds".

Ask the agent:  "opendevops-demo-timeout is failing intermittently, why?"
Expect: get_log_events ("Task timed out") + get_lambda_function_config (timeout_s=1)
+ lookup_cloudtrail_events (UpdateFunctionConfiguration).

  uv run python demos/m2_timeout_misconfig.py setup
  uv run python demos/m2_timeout_misconfig.py teardown
"""

from __future__ import annotations

import _common as c

FN = f"{c.PREFIX}-timeout"
ROLE = f"{c.PREFIX}-basic-role"
BASIC = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

CODE = """
import time
def handler(event, context):
    time.sleep(3)        # simulates a slow downstream call
    return {"ok": True}
"""


def setup() -> None:
    sess = c.session()
    c.whoami(sess)
    role = c.ensure_role(sess, ROLE, [BASIC])
    c.create_lambda(sess, FN, CODE, role, timeout=10)
    c.log("deployed with 10s timeout — clean run")
    c.invoke_n(sess, FN, n=3)

    lam = sess.client("lambda")
    lam.update_function_configuration(FunctionName=FN, Timeout=1)
    lam.get_waiter("function_updated_v2").wait(FunctionName=FN)
    c.log("lowered timeout to 1s (the misconfiguration)")
    c.invoke_n(sess, FN, n=6)
    c.log("DONE. Investigate: 'opendevops-demo-timeout is failing, why?'")


def teardown() -> None:
    sess = c.session()
    c.delete_lambda(sess, FN)
    c.delete_role(sess, ROLE)


if __name__ == "__main__":
    action = c.parse_action(__doc__)
    setup() if action == "setup" else teardown()
