"""Unit tests for the runner's final-message salvage (demos/eval/run.py).

The runner is integration-only, but ``_salvage_submit_json`` is a pure parser
and the single thing standing between "model gave the right answer" and a FAIL
when a model (notably gpt-oss) emits the ``submit_investigation`` payload as
JSON text instead of a tool call. Pin its behavior so a contributor editing the
brace-matching logic sees a clear failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_EVAL_DIR = Path(__file__).resolve().parents[4] / "demos" / "eval"
sys.path.insert(0, str(_EVAL_DIR))

from run import _salvage_submit_json  # noqa: E402


def test_plain_json_dump_is_recovered():
    """The common gpt-oss case: the whole message is the submit payload."""
    payload = {
        "root_cause_category": "SYSTEM_CHANGE",
        "root_cause_summary": "bad image tag",
        "evidence": ["ECS service reports desired=1, running=0"],
    }
    got = _salvage_submit_json(json.dumps(payload))
    assert got == payload


def test_json_wrapped_in_prose_and_fences_is_recovered():
    """Some models wrap the JSON in explanatory prose and/or ``` fences."""
    payload = {"root_cause_category": "RESOURCE_LIMIT", "evidence": ["x"]}
    msg = f"Here is my analysis.\n```json\n{json.dumps(payload)}\n```\nDone."
    assert _salvage_submit_json(msg) == payload


def test_braces_and_quotes_inside_string_values_dont_break_matching():
    """A traceback in the summary contains both quotes and braces — the
    string-aware brace matcher must not miscount depth on those."""
    payload = {
        "root_cause_summary": 'KeyError at user = event["user_id"] with {braces}',
        "root_cause_category": "COMPONENT_FAILURE",
        "evidence": ["a", "b"],
    }
    msg = "Some prose. " + json.dumps(payload) + " trailing words."
    assert _salvage_submit_json(msg) == payload


def test_prose_without_schema_returns_empty():
    """A fallback message ('see tool calls') must NOT be mistaken for an answer."""
    assert _salvage_submit_json("Investigation complete. See tool calls for details.") == {}


def test_non_schema_json_object_is_ignored():
    """A JSON object that lacks the investigation keys is not a submit payload."""
    assert _salvage_submit_json('{"foo": 1, "bar": [2, 3]}') == {}


def test_empty_input_returns_empty():
    assert _salvage_submit_json("") == {}
