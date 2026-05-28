"""Per-request Azure credential resolution for the bash `az` CLI path.

Azure support is CLI-first: the agent investigates Azure through `az` (and `kubectl` for AKS)
via the bash tool, not structured SDK tools. Unlike AWS (which reads creds from env vars),
the Azure CLI is **stateful** — it needs `az login`, which writes tokens to AZURE_CONFIG_DIR.
So per-org `az` runs in an **isolated, cached config dir** with a one-time service-principal
login, never a shared ~/.azure.

The active account comes from the same contextvar the AWS resolver uses
(`get_current_cloud_account`); the account dict's `provider` field disambiguates. Azure accounts
look like::

    {"provider": "azure", "auth_method": "service_principal",
     "config": {"tenant_id": "...", "client_id": "...", "subscription_id": "..."},
     "secret_enc": <Fernet({"client_secret": "..."})>, "id": "..."}
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

from cachetools import TTLCache

from opendevops_core.providers.aws.credentials import _account_secrets, account_for_provider

# Identities that already have a logged-in AZURE_CONFIG_DIR (avoid re-login per tool call).
_login_cache: TTLCache = TTLCache(maxsize=64, ttl=1800)  # 30 min
_BASE_DIR = Path(tempfile.gettempdir()) / "odo-azure"


def current_azure_account() -> dict | None:
    return account_for_provider("azure")


def azure_identity(account: dict) -> str:
    """Stable identity for caching the login/config dir (and not bleeding across orgs)."""
    cfg = account.get("config") or {}
    return cfg.get("client_id") or str(account.get("id") or "azure")


def _sp_fields(account: dict) -> dict:
    cfg = account.get("config") or {}
    secrets = _account_secrets(account)
    return {
        "tenant_id": cfg.get("tenant_id"),
        "client_id": cfg.get("client_id"),
        "subscription_id": cfg.get("subscription_id"),
        # secret lives encrypted in secret_enc; tolerate a plaintext config fallback (no key set).
        "client_secret": secrets.get("client_secret") or cfg.get("client_secret"),
    }


def _config_dir_for(identity: str) -> Path:
    h = hashlib.sha256(identity.encode()).hexdigest()[:16]
    d = _BASE_DIR / h
    d.mkdir(parents=True, exist_ok=True)
    return d


def _az_login(env: dict, sp: dict) -> None:
    """Log the service principal into the isolated AZURE_CONFIG_DIR (our subprocess, not the
    agent's — so it bypasses the bash-tool allowlist intentionally)."""
    login = subprocess.run(
        [
            "az", "login", "--service-principal",
            "-u", sp["client_id"],
            "-p", sp["client_secret"],
            "--tenant", sp["tenant_id"],
            "--only-show-errors",
        ],
        capture_output=True, text=True, timeout=60, env=env,
    )
    if login.returncode != 0:
        raise RuntimeError(f"az login failed: {login.stderr[:300]}")
    if sp.get("subscription_id"):
        subprocess.run(
            ["az", "account", "set", "--subscription", sp["subscription_id"], "--only-show-errors"],
            capture_output=True, text=True, timeout=30, env=env,
        )


def azure_cli_env(account: dict) -> dict:
    """Env for running `az`/`kubectl` as the org's service principal in an isolated, logged-in
    config dir. Raises on missing creds or login failure (caller fails closed)."""
    sp = _sp_fields(account)
    if not (sp["tenant_id"] and sp["client_id"] and sp["client_secret"]):
        raise RuntimeError("Azure account is missing service principal credentials")

    identity = azure_identity(account)
    cfg_dir = _config_dir_for(identity)
    env = dict(os.environ)
    env["AZURE_CONFIG_DIR"] = str(cfg_dir)
    env["HOME"] = str(cfg_dir)  # az + kubectl write under HOME by default; keep it per-org
    env["KUBECONFIG"] = str(cfg_dir / "kubeconfig")  # az aks get-credentials writes here
    if sp["subscription_id"]:
        env["AZURE_SUBSCRIPTION_ID"] = sp["subscription_id"]

    if _login_cache.get(identity) is None:
        _az_login(env, sp)
        _login_cache[identity] = True
    return env


def verify_service_principal(account: dict) -> dict:
    """Validate the SP by acquiring an ARM token (parallel to AWS sts:GetCallerIdentity)."""
    sp = _sp_fields(account)
    if not (sp["tenant_id"] and sp["client_id"] and sp["client_secret"]):
        return {"ok": False, "error": "Missing tenant_id / client_id / client_secret"}
    try:
        from azure.identity import ClientSecretCredential

        cred = ClientSecretCredential(sp["tenant_id"], sp["client_id"], sp["client_secret"])
        token = cred.get_token("https://management.azure.com/.default")
        return {"ok": bool(token and token.token), "subscription_id": sp.get("subscription_id")}
    except Exception as e:  # noqa: BLE001 - surfaced to the admin as a verify failure
        return {"ok": False, "error": str(e)}
