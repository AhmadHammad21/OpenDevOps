"""Sandboxed bash execution tool — whitelisted read-only commands only.

Phase 1: allowlist validation + subprocess with hard timeout.
Phase 2 (planned): throwaway Docker container per command, --network none, --read-only fs.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from typing import Any

from loguru import logger

# AWS CLI read-only operation verbs (the word before the first dash in the operation name).
# Every read-only AWS CLI command starts with one of these — across ALL services.
# e.g. "aws s3api list-buckets", "aws dynamodb describe-table", "aws sns get-topic-attributes"
_AWS_READONLY_VERBS: frozenset[str] = frozenset({
    "describe", "list", "get", "lookup", "filter",
    "search", "scan", "query", "show", "view", "check",
    "batch-get",
})

_COMMAND_MAX_LEN = 2000
_CHAIN_TOKENS: frozenset[str] = frozenset({";", "&&", "||", "|", ">", ">>", "<"})

_AWS_GLOBAL_FLAGS_WITH_VALUE: frozenset[str] = frozenset({
    "--profile",
    "--region",
    "--output",
    "--query",
    "--endpoint-url",
    "--ca-bundle",
    "--cli-connect-timeout",
    "--cli-read-timeout",
})
_AWS_GLOBAL_FLAGS_NO_VALUE: frozenset[str] = frozenset({
    "--debug",
    "--no-cli-pager",
    "--no-verify-ssl",
    "--color",
})
_AWS_BLOCKED_GLOBAL_FLAGS: frozenset[str] = frozenset({"--endpoint-url"})

_KUBECTL_FLAGS_WITH_VALUE: frozenset[str] = frozenset({
    "-n",
    "--namespace",
    "--context",
    "--cluster",
    "--user",
    "--kubeconfig",
    "--server",
    "--request-timeout",
})

_DOCKER_FLAGS_WITH_VALUE: frozenset[str] = frozenset({"-H", "--host", "--context", "--config"})

_TIMEOUT    = 30
_MAX_OUTPUT = 4000
_MAX_STDERR = 1000


def _tokenize(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return []


def _find_subcommand(
    tokens: list[str],
    start_idx: int,
    flags_with_value: frozenset[str],
) -> str | None:
    i = start_idx
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-"):
            if tok in flags_with_value:
                i += 2
                continue
            i += 1
            continue
        return tok.lower()
    return None


def _allowed(command: str, tokens: list[str]) -> bool:
    if not tokens:
        return False
    if len(command) > _COMMAND_MAX_LEN:
        return False
    if any(c in command for c in ("\n", "\r", "\x00")):
        return False
    if any(tok in _CHAIN_TOKENS for tok in tokens):
        return False
    if any(marker in command for marker in ("&&", "||", ";", "|", ">", "<")):
        return False

    binary = tokens[0]

    if binary == "aws":
        # Allow global flags before service/op: aws [flags] <service> <operation>
        i = 1
        while i < len(tokens) and tokens[i].startswith("-"):
            flag = tokens[i].lower()
            if flag in _AWS_BLOCKED_GLOBAL_FLAGS:
                return False
            if flag in _AWS_GLOBAL_FLAGS_WITH_VALUE:
                if i + 1 >= len(tokens):
                    return False
                i += 2
                continue
            if flag in _AWS_GLOBAL_FLAGS_NO_VALUE:
                i += 1
                continue
            # Unknown top-level aws flags are rejected for safety.
            return False

        # Require: aws [flags] <service> <operation>
        if i + 1 >= len(tokens):
            return False
        service = tokens[i]
        operation = tokens[i + 1].lower()
        if service.startswith("-"):
            return False
        # Extract verb = everything before the first dash (e.g. "describe-instances" → "describe")
        verb = operation.split("-")[0]
        # "batch-get-item" → verb fragment is "batch"; check "batch-get" prefix separately
        if operation.startswith("batch-get"):
            return True
        return verb in _AWS_READONLY_VERBS

    if binary == "kubectl":
        subcommand = _find_subcommand(tokens, 1, _KUBECTL_FLAGS_WITH_VALUE)
        return subcommand in {"get", "describe", "logs"}

    if binary == "docker":
        subcommand = _find_subcommand(tokens, 1, _DOCKER_FLAGS_WITH_VALUE)
        return subcommand in {"ps", "logs", "inspect"}

    return False


def run_bash_command(command: str) -> dict[str, Any]:
    """Run a read-only shell command and return structured output.

    Allowed commands:
    - ANY `aws <service> <operation>` where the operation starts with a read-only
      verb: describe-*, list-*, get-*, lookup-*, filter-*, search-*, scan-*, query*,
      batch-get-*. Covers ALL AWS services (S3, DynamoDB, SNS, SQS, Route53,
      ACM, Secrets Manager, SSM, IAM, etc.) not just the structured boto3 tools.
    - kubectl get / describe / logs
    - docker ps / logs / inspect

    Use for docker and kubectl always (no boto3 equivalent). For AWS, use when
    the structured boto3 tools don't cover the service or query you need.
    Never run any command that modifies state.

    Args:
        command: Read-only shell command to run.
    """
    command = command.strip()
    tokens = _tokenize(command)
    start = time.monotonic()

    if not _allowed(command, tokens):
        logger.warning("bash_tool BLOCKED | cmd={!r}", command)
        return {
            "success": False,
            "output":  "",
            "error":   (
                "Command blocked. AWS commands must use safe global flags and a "
                "read-only operation verb (describe-, list-, get-, lookup-, filter-, "
                "search-, scan-, query, batch-get-). "
                "kubectl: only get/describe/logs. docker: only ps/logs/inspect."
            ),
            "command": command,
            "blocked": True,
        }

    logger.info("bash_tool RUN | cmd={!r}", command)
    try:
        proc = subprocess.run(
            tokens,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
        elapsed = time.monotonic() - start
        success = proc.returncode == 0
        logger.info(
            "bash_tool DONE | rc={} elapsed={:.2f}s cmd={!r}",
            proc.returncode, elapsed, command,
        )
        return {
            "success": success,
            "output":  proc.stdout[:_MAX_OUTPUT],
            "error":   proc.stderr[:_MAX_STDERR] if proc.stderr else "",
            "command": command,
            "blocked": False,
        }

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        logger.warning("bash_tool TIMEOUT | elapsed={:.1f}s cmd={!r}", elapsed, command)
        return {
            "success": False,
            "output":  "",
            "error":   f"Command timed out after {_TIMEOUT}s",
            "command": command,
            "blocked": False,
        }

    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.error("bash_tool ERROR | elapsed={:.1f}s cmd={!r} err={}", elapsed, command, exc)
        return {
            "success": False,
            "output":  "",
            "error":   str(exc),
            "command": command,
            "blocked": False,
        }


ALL_BASH_TOOLS = [run_bash_command]
