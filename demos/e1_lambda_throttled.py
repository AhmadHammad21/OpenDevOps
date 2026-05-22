"""
E1 — Lambda fully throttled (reserved concurrency = 0).

Creates a healthy function, pins reserved concurrency to 0 (= 100% throttle),
then invokes it so the Throttles metric lights up.

Ask the agent:  "my function opendevops-demo-throttled is throttling, why?"
Expect it to call get_lambda_function_config (reserved_concurrency: 0) and load
the lambda-throttling skill.

  uv run python demos/e1_lambda_throttled.py setup
  uv run python demos/e1_lambda_throttled.py teardown
"""

from __future__ import annotations

import _common as c

FN = f"{c.PREFIX}-throttled"
ROLE = f"{c.PREFIX}-basic-role"
BASIC = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

CODE = """
def handler(event, context):
    return {"ok": True}
"""


def setup() -> None:
    sess = c.session()
    c.whoami(sess)
    role = c.ensure_role(sess, ROLE, [BASIC])
    c.create_lambda(sess, FN, CODE, role)
    sess.client("lambda").put_function_concurrency(
        FunctionName=FN, ReservedConcurrentExecutions=0
    )
    c.log("set reserved concurrency = 0 (fully throttled)")
    c.invoke_n(sess, FN, n=6)
    c.log("DONE. Investigate: 'why is opendevops-demo-throttled throttling?'")


def teardown() -> None:
    sess = c.session()
    c.delete_lambda(sess, FN)
    c.delete_role(sess, ROLE)


if __name__ == "__main__":
    action = c.parse_action(__doc__)
    setup() if action == "setup" else teardown()
