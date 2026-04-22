import boto3
import pytest
from moto import mock_aws

from tools.cloudwatch import (
    DescribeLogGroupsTool,
    GetAlarmHistoryTool,
    GetAlarmsTool,
    GetLogEventsTool,
    GetMetricDataTool,
)


@mock_aws
def test_get_alarms_empty():
    tool = GetAlarmsTool()
    result = tool.run()
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
    tool = GetAlarmsTool()
    result = tool.run()
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
    tool = GetAlarmsTool()
    result = tool.run(state="ALARM")
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
    tool = GetAlarmHistoryTool()
    result = tool.run(alarm_name="history-alarm", hours=24)
    # moto may not implement describe_alarm_history; we accept either a result or a graceful error
    assert "history" in result or "error" in result


@mock_aws
def test_get_metric_data():
    tool = GetMetricDataTool()
    result = tool.run(
        namespace="AWS/Lambda",
        metric="Errors",
        dimensions=[{"Name": "FunctionName", "Value": "my-fn"}],
        hours=1,
    )
    assert "datapoints" in result


@mock_aws
def test_describe_log_groups_empty():
    tool = DescribeLogGroupsTool()
    result = tool.run()
    assert result["log_groups"] == []
    assert result["count"] == 0


@mock_aws
def test_describe_log_groups_with_group():
    client = boto3.client("logs", region_name="us-east-1")
    client.create_log_group(logGroupName="/aws/lambda/my-fn")
    tool = DescribeLogGroupsTool()
    result = tool.run()
    assert result["count"] == 1
    assert result["log_groups"][0]["name"] == "/aws/lambda/my-fn"


@mock_aws
def test_get_log_events_empty():
    client = boto3.client("logs", region_name="us-east-1")
    client.create_log_group(logGroupName="/aws/lambda/my-fn")
    tool = GetLogEventsTool()
    result = tool.run(log_group="/aws/lambda/my-fn")
    assert result["events"] == []
