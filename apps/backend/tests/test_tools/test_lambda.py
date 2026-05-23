import boto3
from moto import mock_aws

from providers.aws.tools.lambda_ import get_lambda_error_rate, get_lambda_function_config, list_lambda_functions


def _create_lambda_role(iam_client: boto3.client) -> str:
    """Create an IAM role that Lambda can assume (required by moto validation)."""
    import json

    trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )
    role = iam_client.create_role(RoleName="lambda-test-role", AssumeRolePolicyDocument=trust)
    return role["Role"]["Arn"]


@mock_aws
def test_list_functions_empty():
    result = list_lambda_functions()
    assert result["functions"] == []
    assert result["count"] == 0


@mock_aws
def test_list_functions_with_function():
    iam = boto3.client("iam", region_name="us-east-1")
    role_arn = _create_lambda_role(iam)
    client = boto3.client("lambda", region_name="us-east-1")
    client.create_function(
        FunctionName="my-fn",
        Runtime="python3.11",
        Role=role_arn,
        Handler="handler.main",
        Code={"ZipFile": b"fake"},
        MemorySize=256,
        Timeout=30,
    )
    result = list_lambda_functions()
    assert result["count"] == 1
    fn = result["functions"][0]
    assert fn["name"] == "my-fn"
    assert fn["memory_mb"] == 256
    assert fn["timeout_s"] == 30


@mock_aws
def test_get_function_config():
    iam = boto3.client("iam", region_name="us-east-1")
    role_arn = _create_lambda_role(iam)
    client = boto3.client("lambda", region_name="us-east-1")
    client.create_function(
        FunctionName="cfg-fn",
        Runtime="python3.11",
        Role=role_arn,
        Handler="handler.main",
        Code={"ZipFile": b"fake"},
        Environment={"Variables": {"KEY1": "val1", "KEY2": "val2"}},
    )
    result = get_lambda_function_config(name="cfg-fn")
    assert result["name"] == "cfg-fn"
    assert set(result["env_var_keys"]) == {"KEY1", "KEY2"}


@mock_aws
def test_get_lambda_error_rate():
    result = get_lambda_error_rate(name="nonexistent-fn", hours=1)
    assert "total_errors" in result or "error" in result
