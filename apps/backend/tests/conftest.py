import os

import pytest


@pytest.fixture(autouse=True)
def aws_credentials():
    """Stub AWS credentials so moto doesn't need real ones."""
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture(autouse=True)
def clear_tool_cache():
    """Ensure tool-level TTL cache never leaks state between tests."""
    from opendevops_core.tools._cache import _cache

    _cache.clear()
    yield
    _cache.clear()
