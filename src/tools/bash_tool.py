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

# kubectl and docker use exact prefix matching (narrower — fewer read-only verbs to reason about)
_KUBECTL_PREFIXES = ("kubectl get", "kubectl describe", "kubectl logs")
_DOCKER_PREFIXES  = ("docker ps", "docker logs", "docker inspect")

_TIMEOUT    = 30
_MAX_OUTPUT = 4000
_MAX_STDERR = 1000


def _allowed(command: str) -> bool:
    parts = command.split()
    if not parts:
        return False

    binary = parts[0]

    if binary == "aws":
        # Require: aws <service> <operation> — at least 3 tokens
        if len(parts) < 3:
            return False
        operation = parts[2].lower()
        # Extract verb = everything before the first dash (e.g. "describe-instances" → "describe")
        verb = operation.split("-")[0]
        # "batch-get-item" → verb fragment is "batch"; check "batch-get" prefix separately
        if operation.startswith("batch-get"):
            return True
        return verb in _AWS_READONLY_VERBS

    if binary == "kubectl":
        return any(command.startswith(p) for p in _KUBECTL_PREFIXES)

    if binary == "docker":
        return any(command.startswith(p) for p in _DOCKER_PREFIXES)

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
    start = time.monotonic()

    if not _allowed(command):
        logger.warning("bash_tool BLOCKED | cmd={!r}", command)
        return {
            "success": False,
            "output":  "",
            "error":   (
                "Command blocked. AWS commands must use a read-only operation verb "
                "(describe-, list-, get-, lookup-, filter-, search-, scan-, query, batch-get-). "
                "kubectl: only get/describe/logs. docker: only ps/logs/inspect."
            ),
            "command": command,
            "blocked": True,
        }

    logger.info("bash_tool RUN | cmd={!r}", command)
    try:
        proc = subprocess.run(
            shlex.split(command),
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
