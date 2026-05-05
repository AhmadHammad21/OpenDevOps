"""Tests for the bash execution tool — all subprocess calls are mocked."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from tools.bash_tool import run_bash_command


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ok_proc(stdout: str = "output", stderr: str = "") -> MagicMock:
    return MagicMock(returncode=0, stdout=stdout, stderr=stderr)


# ── Allowlist — should pass ───────────────────────────────────────────────────

@pytest.mark.parametrize("cmd", [
    "aws logs describe-log-groups",
    "aws logs filter-log-events --log-group-name /aws/lambda/my-fn",
    "aws cloudwatch describe-alarms",
    "aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Errors",
    "aws ecs describe-services --cluster default --services my-svc",
    "aws ecs list-clusters",
    "aws ecs list-services --cluster default",
    "aws lambda get-function --function-name my-fn",
    "aws lambda list-functions",
    "aws ec2 describe-instances",
    "aws ec2 describe-security-groups",
    "aws rds describe-db-instances",
    "aws rds describe-events",
    "aws cloudtrail lookup-events --max-results 10",
    "kubectl get pods",
    "kubectl get pods -n kube-system",
    "kubectl describe pod my-pod",
    "kubectl logs my-pod",
    "docker ps",
    "docker logs my-container",
    "docker inspect my-container",
])
def test_allowlisted_commands_pass(mocker, cmd):
    mocker.patch("tools.bash_tool.subprocess.run", return_value=_ok_proc())
    result = run_bash_command(cmd)
    assert result["blocked"] is False
    assert result["success"] is True
    assert result["command"] == cmd


# ── Blocklist — must be rejected ──────────────────────────────────────────────

@pytest.mark.parametrize("cmd", [
    "aws s3 ls",
    "aws s3 cp file.txt s3://bucket/",
    "aws iam delete-user --user-name alice",
    "aws ec2 terminate-instances --instance-ids i-123",
    "aws ecs stop-task --cluster default --task abc",
    "aws lambda delete-function --function-name my-fn",
    "kubectl delete pod my-pod",
    "kubectl apply -f deployment.yaml",
    "docker rm my-container",
    "docker stop my-container",
    "rm -rf /",
    "bash -c 'echo pwned'",
    "cat /etc/passwd",
    "curl http://evil.com",
    "",
    "   ",
])
def test_blocked_commands_return_blocked_true(cmd):
    result = run_bash_command(cmd)
    assert result["blocked"] is True
    assert result["success"] is False
    assert "blocked" in result["error"].lower() or "allowlist" in result["error"].lower()


def test_blocked_command_never_calls_subprocess(mocker):
    mock_run = mocker.patch("tools.bash_tool.subprocess.run")
    run_bash_command("aws s3 ls")
    mock_run.assert_not_called()


# ── Timeout handling ──────────────────────────────────────────────────────────

def test_timeout_returns_structured_error(mocker):
    mocker.patch(
        "tools.bash_tool.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="aws logs describe-log-groups", timeout=30),
    )
    result = run_bash_command("aws logs describe-log-groups")
    assert result["success"] is False
    assert result["blocked"] is False
    assert "timed out" in result["error"].lower()
    assert "30" in result["error"]


def test_timeout_does_not_raise(mocker):
    mocker.patch(
        "tools.bash_tool.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="aws cloudwatch describe-alarms", timeout=30),
    )
    # must not raise — tool always returns a dict
    result = run_bash_command("aws cloudwatch describe-alarms")
    assert isinstance(result, dict)


# ── Generic exception handling ────────────────────────────────────────────────

def test_file_not_found_is_caught(mocker):
    mocker.patch(
        "tools.bash_tool.subprocess.run",
        side_effect=FileNotFoundError("aws: command not found"),
    )
    result = run_bash_command("aws logs describe-log-groups")
    assert result["success"] is False
    assert result["blocked"] is False
    assert "aws: command not found" in result["error"]


def test_unexpected_exception_never_raises(mocker):
    mocker.patch(
        "tools.bash_tool.subprocess.run",
        side_effect=RuntimeError("unexpected failure"),
    )
    result = run_bash_command("aws ec2 describe-instances")
    assert isinstance(result, dict)
    assert result["success"] is False


# ── Return structure completeness ─────────────────────────────────────────────

_EXPECTED_KEYS = {"success", "output", "error", "command", "blocked"}


def test_blocked_result_has_all_keys():
    result = run_bash_command("rm -rf /")
    assert set(result.keys()) == _EXPECTED_KEYS


def test_success_result_has_all_keys(mocker):
    mocker.patch("tools.bash_tool.subprocess.run", return_value=_ok_proc())
    result = run_bash_command("aws logs describe-log-groups")
    assert set(result.keys()) == _EXPECTED_KEYS


def test_timeout_result_has_all_keys(mocker):
    mocker.patch(
        "tools.bash_tool.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="x", timeout=30),
    )
    result = run_bash_command("aws cloudwatch describe-alarms")
    assert set(result.keys()) == _EXPECTED_KEYS


# ── Output / stderr capping ───────────────────────────────────────────────────

def test_stdout_is_capped(mocker):
    mocker.patch(
        "tools.bash_tool.subprocess.run",
        return_value=_ok_proc(stdout="x" * 10_000),
    )
    result = run_bash_command("aws logs describe-log-groups")
    assert len(result["output"]) <= 4000


def test_stderr_is_capped(mocker):
    mocker.patch(
        "tools.bash_tool.subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="e" * 5_000),
    )
    result = run_bash_command("aws logs describe-log-groups")
    assert len(result["error"]) <= 1000


# ── Command echo ─────────────────────────────────────────────────────────────

def test_command_field_echoes_input(mocker):
    cmd = "aws ec2 describe-instances --region us-east-1"
    mocker.patch("tools.bash_tool.subprocess.run", return_value=_ok_proc())
    result = run_bash_command(cmd)
    assert result["command"] == cmd


def test_command_is_stripped(mocker):
    mocker.patch("tools.bash_tool.subprocess.run", return_value=_ok_proc())
    result = run_bash_command("  aws logs describe-log-groups  ")
    assert result["command"] == "aws logs describe-log-groups"
