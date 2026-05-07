"""Tests for the tool response capping utility."""

from __future__ import annotations

import json

from tools._cap import cap_tool_result, with_cap


def test_small_result_passes_through():
    result = {"alarms": ["a", "b"], "count": 2}
    assert cap_tool_result(result) is result


def test_large_result_is_capped():
    big = {"events": ["x" * 100] * 1000}
    capped = cap_tool_result(big, max_chars=500)
    assert isinstance(capped, dict)
    assert capped["_capped"] is True
    assert "_notice" in capped
    assert len(capped["_data"]) <= 500


def test_capped_data_is_valid_json_prefix():
    data = {"logs": [{"msg": "hello " * 20}] * 200}
    capped = cap_tool_result(data, max_chars=200)
    assert "_data" in capped
    assert isinstance(capped["_data"], str)


def test_non_dict_passes_through():
    assert cap_tool_result("plain string") == "plain string"
    assert cap_tool_result(None) is None
    assert cap_tool_result([1, 2, 3]) == [1, 2, 3]


def test_original_chars_recorded():
    big = {"k": "v" * 10_000}
    capped = cap_tool_result(big, max_chars=100)
    assert capped["_original_chars"] == len(json.dumps(big))


def test_with_cap_decorator_passes_small_result():
    def my_tool() -> dict:
        return {"count": 1}

    wrapped = with_cap(my_tool)
    assert wrapped() == {"count": 1}


def test_with_cap_decorator_caps_large_result():
    def my_tool() -> dict:
        return {"data": "x" * 50_000}

    wrapped = with_cap(my_tool)
    result = wrapped()
    assert result["_capped"] is True


def test_with_cap_preserves_function_name():
    def get_alarms() -> dict:
        return {}

    wrapped = with_cap(get_alarms)
    assert wrapped.__name__ == "get_alarms"


def test_with_cap_preserves_docstring():
    def get_alarms() -> dict:
        """List CloudWatch alarms."""
        return {}

    wrapped = with_cap(get_alarms)
    assert wrapped.__doc__ == "List CloudWatch alarms."
