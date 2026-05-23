import boto3
from moto import mock_aws
from opendevops_core.providers.aws.tools.ecs import (
    describe_ecs_service,
    list_ecs_clusters,
    list_ecs_services,
)


@mock_aws
def test_list_clusters_empty():
    result = list_ecs_clusters()
    assert result["clusters"] == []
    assert result["count"] == 0


@mock_aws
def test_list_clusters_with_cluster():
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")
    result = list_ecs_clusters()
    assert result["count"] == 1
    assert result["clusters"][0]["name"] == "test-cluster"


@mock_aws
def test_list_services_empty_cluster():
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")
    result = list_ecs_services(cluster="test-cluster")
    assert result["services"] == []
    assert result["count"] == 0


@mock_aws
def test_describe_service_not_found():
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")
    result = describe_ecs_service(cluster="test-cluster", service="nonexistent")
    assert "error" in result
