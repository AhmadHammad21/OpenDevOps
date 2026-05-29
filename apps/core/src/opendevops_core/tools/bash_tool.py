"""Sandboxed bash execution tool — whitelisted read-only commands only.

Phase 1: allowlist validation + subprocess with hard timeout.
Phase 2 (planned): throwaway Docker container per command, --network none, --read-only fs.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from typing import Any

from loguru import logger

from opendevops_core.providers.aws.credentials import (
    current_cloud_accounts,
    resolve_region,
    resolve_session,
)
from opendevops_core.providers.azure.credentials import azure_cli_env

# AWS CLI read-only operation verbs (the word before the first dash in the operation name).
# Every read-only AWS CLI command starts with one of these — across ALL services.
# e.g. "aws s3api list-buckets", "aws dynamodb describe-table", "aws sns get-topic-attributes"
_AWS_READONLY_VERBS: frozenset[str] = frozenset(
    {
        "describe",
        "list",
        "get",
        "lookup",
        "filter",
        "search",
        "scan",
        "query",
        "show",
        "view",
        "check",
        "batch-get",
    }
)

_COMMAND_MAX_LEN = 2000
_CHAIN_TOKENS: frozenset[str] = frozenset({";", "&&", "||", "|", ">", ">>", "<"})

_AWS_GLOBAL_FLAGS_WITH_VALUE: frozenset[str] = frozenset(
    {
        "--profile",
        "--region",
        "--output",
        "--query",
        "--endpoint-url",
        "--ca-bundle",
        "--cli-connect-timeout",
        "--cli-read-timeout",
    }
)
_AWS_GLOBAL_FLAGS_NO_VALUE: frozenset[str] = frozenset(
    {
        "--debug",
        "--no-cli-pager",
        "--no-verify-ssl",
        "--color",
    }
)
_AWS_BLOCKED_GLOBAL_FLAGS: frozenset[str] = frozenset({"--endpoint-url"})

_KUBECTL_FLAGS_WITH_VALUE: frozenset[str] = frozenset(
    {
        "-n",
        "--namespace",
        "--context",
        "--cluster",
        "--user",
        "--kubeconfig",
        "--server",
        "--request-timeout",
    }
)

_DOCKER_FLAGS_WITH_VALUE: frozenset[str] = frozenset({"-H", "--host", "--context", "--config"})

# Azure CLI read-only verbs (the verb is the LAST positional token of the command path,
# e.g. "az aks show" → "show", "az aks get-credentials" → "get", "az monitor metrics list" → "list").
_AZ_READONLY_VERBS: frozenset[str] = frozenset(
    {"list", "show", "get", "check", "describe", "tail", "query", "version"}
)
_AZ_GLOBAL_FLAGS_WITH_VALUE: frozenset[str] = frozenset({"--subscription", "--output", "-o", "--query"})
_AZ_GLOBAL_FLAGS_NO_VALUE: frozenset[str] = frozenset(
    {"--debug", "--verbose", "--only-show-errors", "--help", "-h"}
)

_TIMEOUT = 30
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

    if binary == "az":
        # Consume leading global flags, then the command path is the run of positional tokens
        # up to the first flag; the verb is the last token of that path (az convention).
        i = 1
        while i < len(tokens) and tokens[i].startswith("-"):
            flag = tokens[i].lower()
            if flag in _AZ_GLOBAL_FLAGS_WITH_VALUE:
                if i + 1 >= len(tokens):
                    return False
                i += 2
                continue
            if flag in _AZ_GLOBAL_FLAGS_NO_VALUE:
                i += 1
                continue
            return False
        path: list[str] = []
        while i < len(tokens) and not tokens[i].startswith("-"):
            path.append(tokens[i])
            i += 1
        if not path:
            return False
        verb = path[-1].lower().split("-")[0]  # "get-credentials" → "get"
        return verb in _AZ_READONLY_VERBS

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
    - ANY `az <group...> <verb>` where the verb is read-only: list, show, get-*,
      check, describe, tail, query, version (e.g. `az aks list`, `az monitor metrics list`,
      `az webapp log tail`, `az aks get-credentials`). Covers the Azure surface.
    - kubectl get / describe / logs  (works against AKS after `az aks get-credentials`)
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
            "output": "",
            "error": (
                "Command blocked. AWS commands must use safe global flags and a "
                "read-only operation verb (describe-, list-, get-, lookup-, filter-, "
                "search-, scan-, query, batch-get-). "
                "kubectl: only get/describe/logs. docker: only ps/logs/inspect."
            ),
            "command": command,
            "blocked": True,
        }

    logger.info("bash_tool RUN | cmd={!r}", command)

    # Resolve credentials per command, against the org's connected account for that command's
    # cloud. Tri-state on the contextvar (set in product chat.py; never set in OSS):
    #   None  -> ambient mode (OSS / self-host); run_env stays None, subprocess inherits host env.
    #   {}    -> product tenant with no Cloud Account connected; deny all cloud binaries
    #            (do NOT fall back to platform creds — that would be a cross-tenant leak).
    #   {p:a} -> per-provider resolution: each binary uses its own provider's account, fail
    #            closed when an org has connected clouds but not the one this binary needs.
    accounts = current_cloud_accounts()
    binary = tokens[0]
    run_env = None

    def _blocked(msg: str) -> dict[str, Any]:
        return {"success": False, "output": "", "error": msg, "command": command, "blocked": True}

    cloud_binary = binary in ("aws", "az", "kubectl")
    if accounts == {} and cloud_binary:
        return _blocked(
            f"{binary} is not available — no cloud account is connected for this organization."
        )

    if accounts and binary == "aws":
        if accounts.get("aws") is not None:
            try:
                frozen = resolve_session().get_credentials().get_frozen_credentials()
                run_env = {k: v for k, v in os.environ.items() if k != "AWS_PROFILE"}
                run_env["AWS_ACCESS_KEY_ID"] = frozen.access_key
                run_env["AWS_SECRET_ACCESS_KEY"] = frozen.secret_key
                region = resolve_region()
                run_env["AWS_REGION"] = run_env["AWS_DEFAULT_REGION"] = region
                if frozen.token:
                    run_env["AWS_SESSION_TOKEN"] = frozen.token
                else:
                    run_env.pop("AWS_SESSION_TOKEN", None)
            except Exception as e:  # noqa: BLE001 - fail closed; do not leak platform creds
                logger.error("bash_tool: could not resolve org AWS creds: {}", e)
                return _blocked(f"Could not resolve organization AWS credentials: {e}")
        else:
            return _blocked(
                "AWS is not available for this organization (no AWS account connected)."
            )
    elif accounts and binary == "az":
        if accounts.get("azure") is not None:
            try:
                run_env = azure_cli_env(accounts["azure"])
            except Exception as e:  # noqa: BLE001 - fail closed
                logger.error("bash_tool: could not resolve org Azure creds: {}", e)
                return _blocked(f"Could not resolve organization Azure credentials: {e}")
        else:
            return _blocked(
                "Azure is not available for this organization (no Azure account connected)."
            )
    elif accounts and binary == "kubectl" and accounts.get("azure") is not None:
        # AKS: kubectl must read the per-org kubeconfig written by `az aks get-credentials`
        # into the org's isolated config dir.
        try:
            run_env = azure_cli_env(accounts["azure"])
        except Exception as e:  # noqa: BLE001 - fail closed
            logger.error("bash_tool: could not resolve org Azure creds for kubectl: {}", e)
            return _blocked(f"Could not resolve organization Azure credentials: {e}")

    # Resolve the binary explicitly. On Windows, subprocess.run([...]) with shell=False
    # calls CreateProcess, which only auto-appends `.exe` — so `az` (shipped as `az.cmd` by
    # the MSI/winget installer) is not found. shutil.which honors PATHEXT and PATH from
    # run_env when supplied.
    exe = shutil.which(tokens[0], path=(run_env or os.environ).get("PATH"))
    if exe is None:
        return _blocked(f"{tokens[0]} not found on PATH")
    resolved_tokens = [exe, *tokens[1:]]

    try:
        proc = subprocess.run(
            resolved_tokens,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            env=run_env,
        )
        elapsed = time.monotonic() - start
        success = proc.returncode == 0
        logger.info(
            "bash_tool DONE | rc={} elapsed={:.2f}s cmd={!r}",
            proc.returncode,
            elapsed,
            command,
        )
        return {
            "success": success,
            "output": proc.stdout[:_MAX_OUTPUT],
            "error": proc.stderr[:_MAX_STDERR] if proc.stderr else "",
            "command": command,
            "blocked": False,
        }

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        logger.warning("bash_tool TIMEOUT | elapsed={:.1f}s cmd={!r}", elapsed, command)
        return {
            "success": False,
            "output": "",
            "error": f"Command timed out after {_TIMEOUT}s",
            "command": command,
            "blocked": False,
        }

    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.error("bash_tool ERROR | elapsed={:.1f}s cmd={!r} err={}", elapsed, command, exc)
        return {
            "success": False,
            "output": "",
            "error": str(exc),
            "command": command,
            "blocked": False,
        }


ALL_BASH_TOOLS = [run_bash_command]
