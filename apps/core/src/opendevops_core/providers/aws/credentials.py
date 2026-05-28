"""Per-request AWS credential resolution.

A ContextVar carries the "current cloud account" for the in-flight agent run. Each chat /
investigation runs in its own asyncio task, so the contextvar isolates concurrent requests
from different orgs. Synchronous tool code calls ``get_client()`` / ``resolve_session()`` and
gets the right boto3 session + region without threading ``org_id`` through every tool
signature.

When no account is set (OSS, or an unconfigured install) it falls back to the global
settings — ``AWS_PROFILE`` or the default credential chain — i.e. exactly the prior behavior.

Account dicts come from ``db.get_default_cloud_account()`` and look like::

    {"provider": "aws", "auth_method": "assume_role", "region": "us-east-1",
     "config": {"role_arn": "arn:aws:iam::...:role/...", "external_id": "..."},
     "secret_enc": None, "id": "...", ...}
"""

from __future__ import annotations

import contextvars
import json
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from cachetools import TTLCache
from loguru import logger

from opendevops_core.config import settings

# Map of provider -> active cloud account for this request (or None = env/profile fallback).
# An org can have several connected clouds active at once (e.g. AWS + Azure); each cloud's
# tools resolve credentials against that provider's account independently.
_current_accounts: contextvars.ContextVar[dict[str, dict] | None] = contextvars.ContextVar(
    "current_cloud_accounts", default=None
)

# Assumed-role sessions are cached briefly so a single investigation (many tool calls)
# doesn't re-assume the role on every call. Keyed by credential identity.
_session_cache: TTLCache = TTLCache(maxsize=64, ttl=1800)  # 30 min


def set_current_cloud_accounts(accounts: list[dict]) -> contextvars.Token:
    """Activate the org's connected accounts (one per provider) for this task."""
    by_provider = {a.get("provider", "aws"): a for a in accounts if a}
    return _current_accounts.set(by_provider)


def set_current_cloud_account(account: dict | None) -> contextvars.Token:
    """Convenience: activate a single account (one provider). Back-compatible."""
    return _current_accounts.set({account.get("provider", "aws"): account} if account else {})


def reset_current_cloud_account(token: contextvars.Token) -> None:
    _current_accounts.reset(token)


def current_cloud_accounts() -> dict[str, dict]:
    """The provider->account map active for this task ({} when none)."""
    return _current_accounts.get() or {}


def account_for_provider(provider: str) -> dict | None:
    return current_cloud_accounts().get(provider)


def get_current_cloud_account() -> dict | None:
    """Back-compat single-account accessor: prefer AWS, else any active account, else None."""
    accts = current_cloud_accounts()
    if not accts:
        return None
    return accts.get("aws") or next(iter(accts.values()))


def current_credential_identity() -> str:
    """Stable identity for the tool cache key. The cached structured tools are AWS-only, so
    this keys to the active AWS account (or the global profile) — keeping cached AWS results
    from bleeding across orgs/accounts."""
    acct = account_for_provider("aws")
    if acct:
        cfg = acct.get("config") or {}
        return cfg.get("role_arn") or str(acct.get("id") or "account")
    return f"profile:{settings.aws_profile or 'default'}"


def resolve_region() -> str:
    """Region for the active AWS account, else the global runtime region."""
    acct = account_for_provider("aws")
    if acct and acct.get("region"):
        return acct["region"]
    # Imported lazily to avoid a provider->agent import cycle.
    from opendevops_core.agent.init_store import get_runtime_aws_region

    return get_runtime_aws_region()


def _base_session() -> boto3.Session:
    """The host's own identity — AWS_PROFILE or the default chain. Also the principal that
    assumes customer roles in the product."""
    return (
        boto3.Session(profile_name=settings.aws_profile)
        if settings.aws_profile
        else boto3.Session()
    )


def encrypt_secret(data: dict) -> str | None:
    """Fernet-encrypt a secrets dict for storage in ``cloud_accounts.secret_enc``.

    Returns None when there's nothing to store, or when no encryption key is configured
    (callers should then fall back to a non-secret field or reject the request).
    """
    if not data:
        return None
    key = settings.credentials_encryption_key
    if not key:
        logger.warning("CREDENTIALS_ENCRYPTION_KEY not set; cannot encrypt account secret")
        return None
    from cryptography.fernet import Fernet

    return Fernet(key.encode()).encrypt(json.dumps(data).encode()).decode()


def _account_secrets(account: dict) -> dict:
    """Decrypt and parse the account's secret blob, or {} when none / no key configured."""
    blob = account.get("secret_enc")
    key = settings.credentials_encryption_key
    if not blob or not key:
        return {}
    try:
        from cryptography.fernet import Fernet

        return json.loads(Fernet(key.encode()).decrypt(blob.encode()).decode())
    except Exception as e:  # noqa: BLE001 - never leak crypto errors into tool output
        logger.error("Failed to decrypt cloud account secret: {}", e)
        return {}


def _assume_role_session(account: dict) -> boto3.Session:
    cfg = account.get("config") or {}
    secrets = _account_secrets(account)
    role_arn = cfg.get("role_arn")
    if not role_arn:
        logger.warning("assume_role account {} has no role_arn; using base creds", account.get("id"))
        return _base_session()
    external_id = secrets.get("external_id") or cfg.get("external_id")
    region = resolve_region()

    sts = _base_session().client("sts", region_name=region)
    params: dict[str, Any] = {"RoleArn": role_arn, "RoleSessionName": "opendevops-agent"}
    if external_id:
        params["ExternalId"] = external_id
    creds = sts.assume_role(**params)["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=region,
    )


def _access_key_session(account: dict) -> boto3.Session:
    secrets = _account_secrets(account)
    access_key = secrets.get("access_key_id")
    secret_key = secrets.get("secret_access_key")
    if not access_key or not secret_key:
        logger.warning("access_key account {} missing keys; using base creds", account.get("id"))
        return _base_session()
    return boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=secrets.get("session_token"),
        region_name=resolve_region(),
    )


def resolve_session() -> boto3.Session:
    """The boto3 session for the active AWS account, or the base session when nothing is set."""
    accts = current_cloud_accounts()
    if not accts:
        return _base_session()  # OSS / unscoped -> ambient env/profile creds

    account = accts.get("aws")
    if account is None:
        # Fail closed: the org has connected clouds but no AWS account, so AWS access must NOT
        # fall back to the platform's base credentials (that would leak the platform account).
        raise RuntimeError(
            "AWS is not available for this organization (no AWS account connected)."
        )

    identity = current_credential_identity()
    cached = _session_cache.get(identity)
    if cached is not None:
        return cached

    method = account.get("auth_method")
    try:
        if method == "assume_role":
            session = _assume_role_session(account)
        elif method == "access_key":
            session = _access_key_session(account)
        else:
            logger.warning("Unknown auth_method '{}'; using base creds", method)
            session = _base_session()
    except (BotoCoreError, ClientError) as e:
        logger.error("Failed to resolve creds for account {}: {}", account.get("id"), e)
        raise

    _session_cache[identity] = session
    return session


def get_client(service: str, region: str | None = None) -> Any:
    """boto3 client for `service` using the active account's creds + region."""
    return resolve_session().client(service, region_name=region or resolve_region())
