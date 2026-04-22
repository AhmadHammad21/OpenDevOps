import boto3
import pytest
from moto import mock_aws

from tools.rds import DescribeDBInstancesTool, GetDBEventsTool


@mock_aws
def test_describe_rds_instances_empty():
    tool = DescribeDBInstancesTool()
    result = tool.run()
    assert result["instances"] == []
    assert result["count"] == 0


@mock_aws
def test_describe_rds_instances_with_db():
    client = boto3.client("rds", region_name="us-east-1")
    client.create_db_instance(
        DBInstanceIdentifier="mydb",
        DBInstanceClass="db.t3.micro",
        Engine="mysql",
        MasterUsername="admin",
        MasterUserPassword="password123",
        AllocatedStorage=20,
    )
    tool = DescribeDBInstancesTool()
    result = tool.run()
    assert result["count"] == 1
    assert result["instances"][0]["identifier"] == "mydb"


@mock_aws
def test_get_rds_events_empty():
    tool = GetDBEventsTool()
    result = tool.run(hours=1)
    assert "events" in result
