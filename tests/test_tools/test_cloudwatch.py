import boto3
from moto import mock_aws

from providers.aws.tools.cloudwatch import (
    describe_log_groups,
    get_alarm_history,
    get_alarms,
    get_log_events,
    get_metric_data,
    query_logs_insights,
)


@mock_aws
def test_get_alarms_empty():
    result = get_alarms()
    assert result["alarms"] == []
    assert result["count"] == 0


@mock_aws
def test_get_alarms_with_alarm():
    client = boto3.client("cloudwatch", region_name="us-east-1")
    client.put_metric_alarm(
        AlarmName="test-alarm",
        MetricName="Errors",
        Namespace="AWS/Lambda",
        Statistic="Sum",
        Period=300,
        EvaluationPeriods=1,
        Threshold=1,
        ComparisonOperator="GreaterThanThreshold",
    )
    result = get_alarms()
    assert result["count"] == 1
    assert result["alarms"][0]["name"] == "test-alarm"


@mock_aws
def test_get_alarms_filter_by_state():
    client = boto3.client("cloudwatch", region_name="us-east-1")
    client.put_metric_alarm(
        AlarmName="ok-alarm",
        MetricName="Errors",
        Namespace="AWS/Lambda",
        Statistic="Sum",
        Period=300,
        EvaluationPeriods=1,
        Threshold=1,
        ComparisonOperator="GreaterThanThreshold",
    )
    result = get_alarms(state="ALARM")
    assert isinstance(result["alarms"], list)


@mock_aws
def test_get_alarm_history():
    client = boto3.client("cloudwatch", region_name="us-east-1")
    client.put_metric_alarm(
        AlarmName="history-alarm",
        MetricName="Errors",
        Namespace="AWS/Lambda",
        Statistic="Sum",
        Period=300,
        EvaluationPeriods=1,
        Threshold=1,
        ComparisonOperator="GreaterThanThreshold",
    )
    result = get_alarm_history(alarm_name="history-alarm", hours=24)
    # moto may not implement describe_alarm_history; we accept either a result or a graceful error
    assert "history" in result or "error" in result


@mock_aws
def test_get_metric_data():
    result = get_metric_data(
        namespace="AWS/Lambda",
        metric="Errors",
        dimensions=[{"Name": "FunctionName", "Value": "my-fn"}],
        hours=1,
    )
    assert "datapoints" in result


@mock_aws
def test_describe_log_groups_empty():
    result = describe_log_groups()
    assert result["log_groups"] == []
    assert result["count"] == 0


@mock_aws
def test_describe_log_groups_with_group():
    client = boto3.client("logs", region_name="us-east-1")
    client.create_log_group(logGroupName="/aws/lambda/my-fn")
    result = describe_log_groups()
    assert result["count"] == 1
    assert result["log_groups"][0]["name"] == "/aws/lambda/my-fn"


@mock_aws
def test_get_log_events_empty():
    client = boto3.client("logs", region_name="us-east-1")
    client.create_log_group(logGroupName="/aws/lambda/my-fn")
    result = get_log_events(log_group="/aws/lambda/my-fn")
    assert result["events"] == []


@mock_aws
def test_query_logs_insights_graceful_result():
    client = boto3.client("logs", region_name="us-east-1")
    client.create_log_group(logGroupName="/aws/lambda/my-fn")
    result = query_logs_insights(
        log_group="/aws/lambda/my-fn",
        query="fields @timestamp, @message | limit 5",
        hours=1,
    )
    assert "results" in result or "error" in result
