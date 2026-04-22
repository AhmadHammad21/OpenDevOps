import boto3
import pytest
from moto import mock_aws

from tools.ecs import DescribeServiceTool, ListServicesTool


@mock_aws
def test_list_services_empty_cluster():
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")
    tool = ListServicesTool()
    result = tool.run(cluster="test-cluster")
    assert result["services"] == []
    assert result["count"] == 0


@mock_aws
def test_describe_service_not_found():
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")
    tool = DescribeServiceTool()
    result = tool.run(cluster="test-cluster", service="nonexistent")
    assert "error" in result
