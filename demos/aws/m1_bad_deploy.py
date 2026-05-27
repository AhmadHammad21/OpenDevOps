"""
M1 — Bad deploy (the flagship correlation demo).

Deploys a HEALTHY function and invokes it cleanly, waits, then ships BROKEN code
(UpdateFunctionCode) and invokes again so errors begin right after the deploy.
The money shot: the agent lines up the error onset with the CloudTrail
UpdateFunctionCode event ("errors started at HH:MM, exactly when the deploy ran").

NOTE: CloudTrail management events can take 5-15 min to appear in Event history.
Run setup, grab a coffee, then investigate so the deploy event is queryable.

Ask the agent:  "opendevops-demo-deploy started erroring, did something change?"
Expect: get_lambda_error_rate + get_log_events + lookup_cloudtrail_events.

  uv run python demos/m1_bad_deploy.py setup
  uv run python demos/m1_bad_deploy.py teardown
"""

from __future__ import annotations

import time

import _common as c

FN = f"{c.PREFIX}-deploy"
ROLE = f"{c.PREFIX}-basic-role"
BASIC = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

GOOD = """
def handler(event, context):
    return {"status": "ok", "version": "1.0"}
"""

BAD = """
import json
def handler(event, context):
    cfg = json.loads("{ this is not valid json }")   # introduced in v2.0
    return {"status": "ok", "cfg": cfg}
"""


def setup() -> None:
    sess = c.session()
    c.whoami(sess)
    role = c.ensure_role(sess, ROLE, [BASIC])

    c.create_lambda(sess, FN, GOOD, role)
    c.log("deployed v1.0 (healthy) — sending clean traffic")
    c.invoke_n(sess, FN, n=5)

    c.log("waiting 30s to separate the clean window from the bad deploy...")
    time.sleep(30)

    c.update_lambda_code(sess, FN, BAD)
    c.log("deployed v2.0 (broken) — sending traffic")
    c.invoke_n(sess, FN, n=8)
    c.log("DONE. Wait ~10 min for CloudTrail, then ask: 'did something change?'")


def teardown() -> None:
    sess = c.session()
    c.delete_lambda(sess, FN)
    c.delete_role(sess, ROLE)


if __name__ == "__main__":
    action = c.parse_action(__doc__)
    setup() if action == "setup" else teardown()
