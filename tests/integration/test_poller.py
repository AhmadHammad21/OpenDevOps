"""Integration test for the proactive poller.

Tests the full dispatch flow: fake alarm detected → investigation → Slack post.
Patches AWS data and the agent investigation so no real infra is needed.
"""

import asyncio
import sys
from unittest.mock import patch, AsyncMock

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

FAKE_ALARM = {
    "alarms": [
        {
            "name": "HighErrorRate-payment-processor",
            "reason": "Threshold Crossed: 3 datapoints were greater than threshold (5.0). Most recent: [18.4, 21.2, 19.8].",
            "metric": "Errors",
        }
    ]
}

FAKE_INVESTIGATION_RESULT = {
    "root_cause_category": "RESOURCE_LIMIT",
    "root_cause_summary": (
        "Lambda function payment-processor exceeded its concurrency limit during a traffic spike, "
        "causing invocations to be throttled and error rate to climb above 18%."
    ),
    "confidence": "HIGH",
    "evidence": [
        "CloudWatch alarm HighErrorRate-payment-processor crossed threshold at 18.4 errors/min",
        "Concurrent executions metric shows saturation at reserved limit of 50",
        "No recent deployments found in CloudTrail — config unchanged",
    ],
    "mitigation_steps": [
        "Increase reserved concurrency limit from 50 to 150 for payment-processor",
        "Add SQS queue in front of the Lambda to absorb traffic spikes",
        "Set a CloudWatch alarm on ConcurrentExecutions at 80% of reserved limit",
    ],
    "validation_steps": [
        "Confirm error rate drops below 1% after concurrency increase",
        "Monitor throttle count metric for 15 minutes post-change",
    ],
    "services_affected": ["Lambda", "CloudWatch"],
    "recommended_follow_up": "Review traffic patterns over the last 7 days to right-size concurrency limit.",
}


async def main():
    from agent.config import settings
    from agent.db import db
    from agent.core import init_agent

    if not settings.slack_webhook_url:
        print("SLACK_WEBHOOK_URL not set — Slack post will be skipped.")

    print("Initialising agent…")
    checkpointer = await db.init()
    init_agent(checkpointer)

    print("Running _check_alarms() with a fake alarm + fake investigation…")
    with (
        patch("tools.cloudwatch.get_alarms", return_value=FAKE_ALARM),
        patch("agent.poller._run_investigation", new=AsyncMock(return_value=FAKE_INVESTIGATION_RESULT)),
    ):
        from agent.poller import _check_alarms
        await _check_alarms()

    print("Done. Check your Slack channel.")
    await db.close()


asyncio.run(main())
