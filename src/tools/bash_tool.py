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

# Only commands starting with these prefixes are permitted.
# Any other command is rejected before subprocess is ever called.
_ALLOWLIST: tuple[str, ...] = (
    "aws logs ",
    "aws cloudwatch ",
    "aws ecs describe",
    "aws ecs list",
    "aws lambda get",
    "aws lambda list",
    "aws ec2 describe",
    "aws rds describe",
    "aws cloudtrail lookup",
    "kubectl get",
    "kubectl describe",
    "kubectl logs",
    "docker ps",
    "docker logs",
    "docker inspect",
)

_TIMEOUT = 30
_MAX_OUTPUT = 4000
_MAX_STDERR = 1000


def _allowed(command: str) -> bool:
    return any(command.startswith(p) for p in _ALLOWLIST)


def run_bash_command(command: str) -> dict[str, Any]:
    """Run a whitelisted read-only shell command and return structured output.

    Allowed prefixes: aws logs, aws cloudwatch, aws ecs describe/list,
    aws lambda get/list, aws ec2 describe, aws rds describe,
    aws cloudtrail lookup, kubectl get/describe/logs,
    docker ps/logs/inspect.

    Use this tool only when the boto3 AWS tools cannot provide the information
    you need. Always prefer the existing AWS tools first — this is a last resort.
    Never suggest or run any command that modifies state.

    Args:
        command: Read-only shell command to run. Must match the allowlist.
    """
    command = command.strip()
    start = time.monotonic()

    if not _allowed(command):
        logger.warning("bash_tool BLOCKED | cmd={!r}", command)
        return {
            "success": False,
            "output":  "",
            "error":   (
                "Command blocked — not on the allowlist. "
                f"Allowed prefixes: {', '.join(_ALLOWLIST)}"
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
