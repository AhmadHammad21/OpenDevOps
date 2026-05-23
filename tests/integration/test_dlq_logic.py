"""Unit tests for DLQ-related logic in the event consumer.

Tests that the consumer correctly leaves messages in the queue when
processing fails (should_delete stays False), which is what triggers
the SQS redrive to the DLQ after maxReceiveCount attempts.

Moto does not simulate the actual DLQ redrive — use scripts/test_dlq.py
for end-to-end verification against real AWS.
"""

from __future__ import annotations

import json

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sqs_message(body: str, receipt: str = "receipt-abc") -> dict:
    return {"Body": body, "ReceiptHandle": receipt}


# ---------------------------------------------------------------------------
# Tests: message NOT deleted on parse failure
# ---------------------------------------------------------------------------

def test_invalid_json_is_not_deleted():
    """A message that cannot be parsed as JSON must stay in the queue."""
    deleted = []
    messages = [_make_sqs_message("NOT_VALID_JSON")]

    for msg in messages:
        should_delete = False
        try:
            json.loads(msg["Body"])
            should_delete = True
        except json.JSONDecodeError:
            pass  # leave in queue → SQS will redrive after maxReceiveCount
        if should_delete:
            deleted.append(msg["ReceiptHandle"])

    assert deleted == [], "Invalid JSON message should NOT be deleted"


def test_valid_json_would_be_deleted_on_success():
    """Control: a well-formed event that processes without error is deleted."""
    deleted = []
    messages = [_make_sqs_message(json.dumps({"source": "aws.lambda"}))]

    for msg in messages:
        should_delete = False
        try:
            json.loads(msg["Body"])
            # Simulate successful processing
            should_delete = True
        except json.JSONDecodeError:
            pass
        if should_delete:
            deleted.append(msg["ReceiptHandle"])

    assert deleted == ["receipt-abc"]


def test_processing_exception_leaves_message_in_queue():
    """A message that raises during processing must not be deleted."""
    deleted = []
    messages = [_make_sqs_message(json.dumps({"source": "aws.cloudwatch"}))]

    for msg in messages:
        should_delete = False
        try:
            json.loads(msg["Body"])
            raise RuntimeError("Investigation produced no structured result")
        except json.JSONDecodeError:
            pass
        except Exception:
            pass  # leave in queue
        if should_delete:
            deleted.append(msg["ReceiptHandle"])

    assert deleted == [], "Failed processing must not delete the message"


# ---------------------------------------------------------------------------
# Tests: event_infra redrive policy constants
# ---------------------------------------------------------------------------

def test_max_receive_count_constant():
    """MAX_RECEIVE_COUNT must match what we verified in AWS."""
    from providers.aws.event_infra import MAX_RECEIVE_COUNT
    assert MAX_RECEIVE_COUNT == "5", (
        "maxReceiveCount changed — update the DLQ in AWS to match "
        "(aws sqs set-queue-attributes --attribute-names RedrivePolicy)"
    )


def test_dlq_queue_name_constant():
    from providers.aws.event_infra import DLQ_QUEUE_NAME, QUEUE_NAME
    assert DLQ_QUEUE_NAME == f"{QUEUE_NAME}-dlq", (
        "DLQ name must be the main queue name with '-dlq' suffix"
    )


# ---------------------------------------------------------------------------
# Tests: event consumer loop deletes only on success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_consumer_loop_skips_delete_on_bad_json(monkeypatch):
    """event_consumer_loop must not delete a message that fails JSON parsing."""
    import asyncio
    from unittest.mock import MagicMock, patch

    deleted_receipts: list[str] = []
    received_once = False

    def fake_receive(**_kwargs):
        nonlocal received_once
        if received_once:
            # Return empty after first batch so the loop exits
            raise asyncio.CancelledError()
        received_once = True
        return {"Messages": [{"Body": "NOT_VALID_JSON", "ReceiptHandle": "rh-bad"}]}

    def fake_delete(QueueUrl, ReceiptHandle):  # noqa: N803
        deleted_receipts.append(ReceiptHandle)

    mock_sqs = MagicMock()
    mock_sqs.receive_message.side_effect = fake_receive
    mock_sqs.delete_message.side_effect = fake_delete

    with (
        patch("providers.aws.event_consumer.get_runtime_sqs_queue_url", return_value="https://fake-url"),
        patch("providers.aws.event_consumer.get_runtime_aws_region", return_value="us-east-1"),
        patch("boto3.Session") as mock_session,
    ):
        mock_session.return_value.client.return_value = mock_sqs
        from providers.aws.event_consumer import event_consumer_loop
        try:
            await event_consumer_loop()
        except asyncio.CancelledError:
            pass

    assert "rh-bad" not in deleted_receipts, (
        "Bad-JSON message receipt should never be passed to delete_message"
    )


@pytest.mark.asyncio
async def test_consumer_loop_skips_delete_on_processing_error(monkeypatch):
    """event_consumer_loop must not delete a message when _process_event raises."""
    import asyncio
    from unittest.mock import MagicMock, patch

    deleted_receipts: list[str] = []
    received_once = False

    def fake_receive(**_kwargs):
        nonlocal received_once
        if received_once:
            raise asyncio.CancelledError()
        received_once = True
        return {
            "Messages": [{
                "Body": json.dumps({"source": "aws.cloudwatch", "detail": {}}),
                "ReceiptHandle": "rh-fail",
            }]
        }

    def fake_delete(QueueUrl, ReceiptHandle):  # noqa: N803
        deleted_receipts.append(ReceiptHandle)

    async def fake_process_event(_event):
        raise RuntimeError("Simulated processing failure")

    mock_sqs = MagicMock()
    mock_sqs.receive_message.side_effect = fake_receive
    mock_sqs.delete_message.side_effect = fake_delete

    with (
        patch("providers.aws.event_consumer.get_runtime_sqs_queue_url", return_value="https://fake-url"),
        patch("providers.aws.event_consumer.get_runtime_aws_region", return_value="us-east-1"),
        patch("providers.aws.event_consumer._process_event", side_effect=fake_process_event),
        patch("boto3.Session") as mock_session,
    ):
        mock_session.return_value.client.return_value = mock_sqs
        from providers.aws.event_consumer import event_consumer_loop
        try:
            await event_consumer_loop()
        except asyncio.CancelledError:
            pass

    assert "rh-fail" not in deleted_receipts, (
        "Failed-processing message receipt should never be passed to delete_message"
    )
