import boto3
from moto import mock_aws
from opendevops_core.providers.aws.tools.rds import describe_rds_instances, get_rds_events


@mock_aws
def test_describe_rds_instances_empty():
    result = describe_rds_instances()
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
    result = describe_rds_instances()
    assert result["count"] == 1
    assert result["instances"][0]["identifier"] == "mydb"


@mock_aws
def test_get_rds_events_empty():
    result = get_rds_events(hours=1)
    assert "events" in result
