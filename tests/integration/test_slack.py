"""Quick standalone test — sends a sample investigation result to Slack."""

import asyncio
from agent.config import settings
from integrations.slack_webhook import post_investigation

SAMPLE_RESULT = {
    "root_cause_category": "RESOURCE_LIMIT",
    "root_cause_summary": (
        "Lambda function payment-processor exceeded its memory limit (512 MB) "
        "during a traffic spike, causing 47 invocations to fail with OOM errors."
    ),
    "confidence": "HIGH",
    "evidence": [
        "CloudWatch: MemoryUtilization hit 99.8% at 14:32 UTC",
        "Lambda logs: 47x 'Runtime exited with error: signal: killed' in the last hour",
        "Error rate jumped from 0.2% → 18.4% at 14:31 UTC",
    ],
    "mitigation_steps": [
        "Increase Lambda memory from 512 MB to 1024 MB",
        "Add a memory utilization alarm at 80% to catch this earlier",
        "Review payload sizes — large S3 objects may be loaded into memory unnecessarily",
    ],
    "services_affected": ["Lambda", "CloudWatch"],
}

async def main():
    if not settings.slack_webhook_url:
        print("SLACK_WEBHOOK_URL is not set in .env — aborting.")
        return

    print(f"Sending test message to Slack webhook …")
    await post_investigation(settings.slack_webhook_url, SAMPLE_RESULT, "test-session-1234")
    print("Done.")

asyncio.run(main())
