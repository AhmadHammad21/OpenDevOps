from __future__ import annotations

from agent.incident_keys import event_incident_key, lambda_metric_incident_key


def test_lambda_event_keys_split_different_error_signatures():
    base_event = {
        "source": "aws.lambda",
        "detail-type": "Lambda Function Invocation Result - Failure",
        "region": "us-east-1",
        "detail": {
            "functionName": "payment-processor",
            "responsePayload": {
                "errorType": "TimeoutError",
                "errorMessage": "request timed out after 30s",
            },
        },
    }
    second_event = {
        **base_event,
        "detail": {
            "functionName": "payment-processor",
            "responsePayload": {
                "errorType": "ValidationError",
                "errorMessage": "missing customer_id",
            },
        },
    }

    assert event_incident_key(base_event) != event_incident_key(second_event)


def test_lambda_metric_key_is_function_scoped():
    assert (
        lambda_metric_incident_key("payment-processor", "us-east-1")
        == "lambda_errors:us-east-1:payment-processor"
    )


def test_cloudwatch_alarm_key_ignores_delivery_time():
    event_a = {
        "source": "aws.cloudwatch",
        "detail-type": "CloudWatch Alarm State Change",
        "region": "us-east-1",
        "time": "2026-05-20T00:00:00Z",
        "detail": {"alarmName": "HighErrorRate"},
    }
    event_b = {**event_a, "time": "2026-05-20T00:05:00Z"}

    assert event_incident_key(event_a) == event_incident_key(event_b)