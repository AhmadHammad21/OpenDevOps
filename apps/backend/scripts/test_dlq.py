#!/usr/bin/env python3
"""
test_dlq.py — verify the SQS → DLQ redrive policy works end-to-end.

Sends a poison message (invalid JSON) to the main queue, then simulates
maxReceiveCount failed processing attempts by receiving the message and
immediately releasing it back each time without deleting it. After the
limit is hit, AWS automatically moves the message to the DLQ.

IMPORTANT: Stop the app server before running this script. If the event
consumer is running it will compete for the poison message, hold it for
the full visibility timeout (180s), and the script will not be able to
reach it. The consumer's behaviour (not deleting bad JSON) is already
covered by the pytest suite — this script only verifies AWS redrive.

Requirements: AWS profile with sqs:SendMessage, sqs:ReceiveMessage,
              sqs:ChangeMessageVisibility, sqs:DeleteMessage on both queues.

Usage:
  uv run python scripts/test_dlq.py --profile my-write-profile
  uv run python scripts/test_dlq.py --profile my-write-profile --region eu-west-1
  uv run python scripts/test_dlq.py --profile my-write-profile --no-cleanup
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import boto3
from botocore.exceptions import ClientError

QUEUE_NAME = "opendevops-agent-events"
DLQ_QUEUE_NAME = "opendevops-agent-events-dlq"
MAX_RECEIVE_COUNT = 5


def _get_queue_url(sqs, name: str) -> str:
    return sqs.get_queue_url(QueueName=name)["QueueUrl"]


def _get_queue_attrs(sqs, queue_url: str) -> dict:
    return sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["RedrivePolicy", "ApproximateNumberOfMessagesNotVisible"],
    )["Attributes"]


def _get_max_receive_count(attrs: dict) -> int:
    policy = json.loads(attrs.get("RedrivePolicy", "{}"))
    return int(policy.get("maxReceiveCount", MAX_RECEIVE_COUNT))


def main(profile: str, region: str, cleanup: bool) -> int:
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    sqs = session.client("sqs", region_name=region)

    print(f"Profile : {profile or 'default'}")
    print(f"Region  : {region}\n")

    try:
        main_url = _get_queue_url(sqs, QUEUE_NAME)
        dlq_url = _get_queue_url(sqs, DLQ_QUEUE_NAME)
    except ClientError as e:
        print(f"✗ Could not resolve queue URLs: {e}")
        print("  Make sure the init wizard has been run (Settings → AWS Configuration).")
        return 1

    main_attrs = _get_queue_attrs(sqs, main_url)
    max_receive = _get_max_receive_count(main_attrs)
    in_flight = int(main_attrs.get("ApproximateNumberOfMessagesNotVisible", 0))

    print(f"Main queue : {main_url}")
    print(f"DLQ        : {dlq_url}")
    print(f"maxReceiveCount : {max_receive}")

    if in_flight > 0:
        print(
            f"\n⚠ WARNING: {in_flight} message(s) currently in-flight on the main queue."
            "\n  If the event consumer is running it will compete for the poison message."
            "\n  Stop the app server first, then re-run this script."
        )
        return 1

    # Unique marker so we can identify our message among any others in the queue
    marker = f"opendevops-dlq-test-{int(time.time())}"
    poison = f"NOT_VALID_JSON [{marker}]"

    try:
        sqs.send_message(QueueUrl=main_url, MessageBody=poison)
    except ClientError as e:
        print(f"\n✗ Failed to send poison message: {e}")
        print("  The profile needs sqs:SendMessage on the main queue.")
        return 1

    print(f"\nSent poison message : {poison}")
    print(f"Simulating {max_receive} failed receive attempts...\n")

    grabbed = False
    for attempt in range(1, max_receive + 2):
        resp = sqs.receive_message(
            QueueUrl=main_url,
            MaxNumberOfMessages=10,
            VisibilityTimeout=2,
            WaitTimeSeconds=5,
            AttributeNames=["ApproximateReceiveCount"],
        )
        target = next(
            (m for m in resp.get("Messages", []) if marker in m["Body"]), None
        )

        if target is None:
            if grabbed:
                print(f"  Attempt {attempt}: message gone from main queue — redrive triggered")
            else:
                # Message was never visible — likely grabbed by event consumer
                print(
                    f"  Attempt {attempt}: message not visible (in-flight)."
                    "\n  The event consumer may have picked it up."
                    "\n  Stop the app server and re-run this script."
                )
                return 1
            break

        grabbed = True
        count = target.get("Attributes", {}).get("ApproximateReceiveCount", "?")
        print(f"  Attempt {attempt}: received (ApproximateReceiveCount={count})")

        # Simulate failed processing: release immediately without deleting
        try:
            sqs.change_message_visibility(
                QueueUrl=main_url,
                ReceiptHandle=target["ReceiptHandle"],
                VisibilityTimeout=0,
            )
        except ClientError:
            pass  # receipt handle may be invalid if visibility already expired

        time.sleep(0.3)

    print("\nWaiting 3s for AWS to complete the redrive...")
    time.sleep(3)

    print("Checking DLQ...")
    dlq_resp = sqs.receive_message(
        QueueUrl=dlq_url,
        MaxNumberOfMessages=10,
        VisibilityTimeout=0,
        WaitTimeSeconds=5,
    )
    dlq_messages = dlq_resp.get("Messages", [])
    hit = next((m for m in dlq_messages if marker in m["Body"]), None)

    if hit:
        print(f"\n✓ PASS — poison message found in DLQ after {max_receive} failed attempts.")
        if cleanup:
            sqs.delete_message(QueueUrl=dlq_url, ReceiptHandle=hit["ReceiptHandle"])
            print("  Test message deleted from DLQ.")
        else:
            print("  Skipping cleanup (--no-cleanup). Message stays in DLQ.")
        return 0

    count = len(dlq_messages)
    print(f"\n✗ FAIL — message not found in DLQ ({count} other message(s) present).")
    print("  The message may still be in the main queue or the redrive is misconfigured.")
    return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify SQS → DLQ redrive end-to-end")
    parser.add_argument("--profile", default="", help="AWS profile name (needs write access)")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument(
        "--no-cleanup",
        dest="cleanup",
        action="store_false",
        help="Leave the test message in the DLQ after the test",
    )
    args = parser.parse_args()
    sys.exit(main(args.profile, args.region, args.cleanup))
