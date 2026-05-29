"""Per-org credential resolution, cache isolation, and multi-cloud fail-closed behavior."""

import pytest
from moto import mock_aws
from opendevops_core.providers.aws import credentials as cred
from opendevops_core.tools._cache import tool_cached


def _azure_account(client_id: str = "client-1") -> dict:
    return {
        "id": "az1",
        "provider": "azure",
        "auth_method": "service_principal",
        "region": "eastus",
        "config": {"tenant_id": "t", "client_id": client_id, "subscription_id": "sub-1"},
        "secret_enc": None,
    }


def _account(role_arn: str, acct_id: str = "acct") -> dict:
    return {
        "id": acct_id,
        "provider": "aws",
        "auth_method": "assume_role",
        "region": "us-east-1",
        "config": {"role_arn": role_arn},
        "secret_enc": None,
    }


def test_identity_fallback_when_no_account():
    # No contextvar set -> falls back to the global profile identity.
    assert cred.get_current_cloud_account() is None
    assert cred.current_credential_identity().startswith("profile:")


def test_identity_uses_role_arn_when_account_set():
    token = cred.set_current_cloud_account(_account("arn:aws:iam::111111111111:role/odo"))
    try:
        assert cred.current_credential_identity() == "arn:aws:iam::111111111111:role/odo"
    finally:
        cred.reset_current_cloud_account(token)
    # Reset restores the fallback.
    assert cred.current_credential_identity().startswith("profile:")


def test_cache_is_isolated_across_accounts():
    calls: list[int] = []

    @tool_cached
    def _probe(x: int) -> dict:
        calls.append(x)
        return {"x": x}

    # Same arg under two different accounts must execute twice (no cross-account bleed).
    t = cred.set_current_cloud_account(_account("arn:aws:iam::111111111111:role/a", "a"))
    _probe(1)
    cred.reset_current_cloud_account(t)

    t = cred.set_current_cloud_account(_account("arn:aws:iam::222222222222:role/b", "b"))
    _probe(1)
    cred.reset_current_cloud_account(t)

    assert calls == [1, 1]

    # Same account + same arg -> served from cache (no third execution).
    t = cred.set_current_cloud_account(_account("arn:aws:iam::111111111111:role/a", "a"))
    _probe(1)
    cred.reset_current_cloud_account(t)

    assert calls == [1, 1]


@mock_aws
def test_assume_role_session_resolves_and_caches():
    cred._session_cache.clear()
    arn = "arn:aws:iam::333333333333:role/odo-assume"
    token = cred.set_current_cloud_account(_account(arn, "c"))
    try:
        s1 = cred.resolve_session()
        s2 = cred.resolve_session()
        # Both calls return the same cached assumed-role session.
        assert s1 is s2
        # The assumed session is usable (moto-backed STS).
        ident = s1.client("sts", region_name="us-east-1").get_caller_identity()
        assert "Arn" in ident
    finally:
        cred.reset_current_cloud_account(token)
        cred._session_cache.clear()


@mock_aws
def test_no_account_uses_base_session():
    cred._session_cache.clear()
    # With no account set, resolve_session returns the base (env/profile) session.
    session = cred.resolve_session()
    ident = session.client("sts", region_name="us-east-1").get_caller_identity()
    assert "Account" in ident


def test_encrypt_secret_noop_without_key():
    # No CREDENTIALS_ENCRYPTION_KEY configured in tests -> nothing to encrypt with.
    assert cred.encrypt_secret({}) is None
    assert cred.encrypt_secret({"external_id": "x"}) is None


def test_encrypt_decrypt_roundtrip(monkeypatch):
    from cryptography.fernet import Fernet
    from opendevops_core.config import get_settings

    key = Fernet.generate_key().decode()
    monkeypatch.setattr(get_settings(), "credentials_encryption_key", key)

    enc = cred.encrypt_secret({"external_id": "ext-123"})
    assert enc and enc != "ext-123"
    assert cred._account_secrets({"secret_enc": enc, "config": {}}) == {"external_id": "ext-123"}


class _Frozen:
    access_key = "AKIAFAKE"
    secret_key = "secretfake"
    token = "sessiontoken"


class _FakeCreds:
    def get_frozen_credentials(self):
        return _Frozen()


class _FakeSession:
    def get_credentials(self):
        return _FakeCreds()


class _CompletedProc:
    returncode = 0
    stdout = "{}"
    stderr = ""


def test_bash_injects_org_creds_for_aws(monkeypatch):
    from opendevops_core.tools import bash_tool

    captured: dict = {}
    monkeypatch.setattr(bash_tool, "resolve_session", lambda: _FakeSession())
    monkeypatch.setattr(
        bash_tool.subprocess,
        "run",
        lambda tokens, **kw: (captured.__setitem__("env", kw.get("env")), _CompletedProc())[1],
    )

    token = cred.set_current_cloud_account(_account("arn:aws:iam::111111111111:role/x"))
    try:
        res = bash_tool.run_bash_command("aws sts get-caller-identity")
    finally:
        cred.reset_current_cloud_account(token)

    assert res["success"]
    env = captured["env"]
    assert env is not None
    assert env["AWS_ACCESS_KEY_ID"] == "AKIAFAKE"
    assert env["AWS_SESSION_TOKEN"] == "sessiontoken"
    assert "AWS_PROFILE" not in env  # platform profile is stripped


def test_bash_no_account_inherits_ambient_env(monkeypatch):
    from opendevops_core.tools import bash_tool

    captured: dict = {}
    monkeypatch.setattr(
        bash_tool.subprocess,
        "run",
        lambda tokens, **kw: (captured.__setitem__("env", kw.get("env")), _CompletedProc())[1],
    )
    res = bash_tool.run_bash_command("aws sts get-caller-identity")
    assert res["success"]
    assert captured["env"] is None  # no account -> inherit the process env (OSS behavior)


def test_bash_fails_closed_when_org_creds_unresolvable(monkeypatch):
    from opendevops_core.tools import bash_tool

    def _boom():
        raise RuntimeError("assume failed")

    monkeypatch.setattr(bash_tool, "resolve_session", _boom)
    token = cred.set_current_cloud_account(_account("arn:aws:iam::111111111111:role/x"))
    try:
        res = bash_tool.run_bash_command("aws sts get-caller-identity")
    finally:
        cred.reset_current_cloud_account(token)

    assert res["success"] is False
    assert res.get("blocked") is True
    assert "credentials" in res["error"].lower()


# ── Multi-cloud (Azure) ──────────────────────────────────────────────────────


def test_resolve_session_fails_closed_for_non_aws_account():
    # An Azure org must NOT fall back to the platform's base AWS creds.
    token = cred.set_current_cloud_account(_azure_account())
    try:
        with pytest.raises(RuntimeError):
            cred.resolve_session()
    finally:
        cred.reset_current_cloud_account(token)


def test_bash_az_allowed_and_blocked():
    from opendevops_core.tools import bash_tool

    assert bash_tool._allowed("az aks list", ["az", "aks", "list"])
    assert bash_tool._allowed(
        "az aks get-credentials -g r -n n", ["az", "aks", "get-credentials", "-g", "r", "-n", "n"]
    )
    assert bash_tool._allowed("az monitor metrics list", ["az", "monitor", "metrics", "list"])
    assert not bash_tool._allowed("az group create", ["az", "group", "create"])
    assert not bash_tool._allowed("az vm delete --name x", ["az", "vm", "delete", "--name", "x"])


def test_bash_injects_azure_env_for_az(monkeypatch):
    from opendevops_core.tools import bash_tool

    captured: dict = {}
    monkeypatch.setattr(
        bash_tool,
        "azure_cli_env",
        lambda account: {"AZURE_CONFIG_DIR": "/tmp/x", "AZURE_SUBSCRIPTION_ID": "sub-1"},
    )
    monkeypatch.setattr(
        bash_tool.subprocess,
        "run",
        lambda tokens, **kw: (captured.__setitem__("env", kw.get("env")), _CompletedProc())[1],
    )
    token = cred.set_current_cloud_account(_azure_account())
    try:
        res = bash_tool.run_bash_command("az aks list")
    finally:
        cred.reset_current_cloud_account(token)

    assert res["success"]
    assert captured["env"]["AZURE_SUBSCRIPTION_ID"] == "sub-1"


def test_bash_blocks_aws_for_azure_org(monkeypatch):
    from opendevops_core.tools import bash_tool

    def _no_run(*a, **k):
        raise AssertionError("subprocess must not run for a cross-provider command")

    monkeypatch.setattr(bash_tool.subprocess, "run", _no_run)
    token = cred.set_current_cloud_account(_azure_account())
    try:
        res = bash_tool.run_bash_command("aws s3api list-buckets")
    finally:
        cred.reset_current_cloud_account(token)
    assert res["success"] is False and res.get("blocked") is True
    assert "aws is not available" in res["error"].lower()


def test_bash_blocks_az_for_aws_org(monkeypatch):
    from opendevops_core.tools import bash_tool

    def _no_run(*a, **k):
        raise AssertionError("subprocess must not run for a cross-provider command")

    monkeypatch.setattr(bash_tool.subprocess, "run", _no_run)
    token = cred.set_current_cloud_account(_account("arn:aws:iam::111111111111:role/x"))
    try:
        res = bash_tool.run_bash_command("az aks list")
    finally:
        cred.reset_current_cloud_account(token)
    assert res["success"] is False and res.get("blocked") is True
    assert "azure is not available" in res["error"].lower()


# ── Multi-cloud: both providers active at once ───────────────────────────────


def test_set_current_cloud_accounts_maps_by_provider():
    token = cred.set_current_cloud_accounts(
        [_account("arn:aws:iam::111111111111:role/x"), _azure_account()]
    )
    try:
        assert cred.account_for_provider("aws")["config"]["role_arn"].endswith("role/x")
        assert cred.account_for_provider("azure")["provider"] == "azure"
    finally:
        cred.reset_current_cloud_account(token)
    assert cred.account_for_provider("aws") is None  # reset clears it


def test_bash_uses_both_clouds_when_both_connected(monkeypatch):
    from opendevops_core.tools import bash_tool

    monkeypatch.setattr(bash_tool, "resolve_session", lambda: _FakeSession())
    monkeypatch.setattr(
        bash_tool,
        "azure_cli_env",
        lambda account: {"AZURE_CONFIG_DIR": "/tmp/x", "AZURE_SUBSCRIPTION_ID": "sub-1"},
    )
    runs: list[tuple] = []
    monkeypatch.setattr(
        bash_tool.subprocess,
        "run",
        lambda tokens, **kw: (runs.append((tokens[0], kw.get("env"))), _CompletedProc())[1],
    )

    token = cred.set_current_cloud_accounts(
        [_account("arn:aws:iam::111111111111:role/x"), _azure_account()]
    )
    try:
        r_aws = bash_tool.run_bash_command("aws s3api list-buckets")
        r_az = bash_tool.run_bash_command("az aks list")
    finally:
        cred.reset_current_cloud_account(token)

    assert r_aws["success"] and r_az["success"]
    # runs[N][0] is the absolute exe path (shutil.which resolved it); match on basename
    # so the test works regardless of where aws/az live (or .exe / .cmd on Windows).
    import os as _os

    env_by_bin = {_os.path.basename(t).split(".")[0]: env for t, env in runs}
    assert env_by_bin["aws"]["AWS_ACCESS_KEY_ID"] == "AKIAFAKE"  # AWS account creds
    assert env_by_bin["az"]["AZURE_SUBSCRIPTION_ID"] == "sub-1"  # Azure account env


# ── Tri-state contextvar: None (ambient) vs {} (explicit empty / fail closed) ──


def test_current_cloud_accounts_is_none_when_unset():
    """OSS / self-host default: contextvar was never set → callers see None, not {}."""
    assert cred.current_cloud_accounts() is None


def test_resolve_session_ambient_when_contextvar_unset(monkeypatch):
    """OSS default behavior is preserved: with no contextvar set, resolve_session falls back
    to _base_session() (the host's ambient env/profile creds)."""
    sentinel = object()
    monkeypatch.setattr(cred, "_base_session", lambda: sentinel)
    cred._session_cache.clear()
    # contextvar is at its default (None); no setter was called.
    assert cred.resolve_session() is sentinel


def test_resolve_session_fails_closed_on_explicit_empty():
    """Product safety net: when the contextvar is explicitly set to {} (e.g. tenant with no
    Cloud Account connected), resolve_session must NOT fall back to platform creds — it raises.
    """
    cred._session_cache.clear()
    token = cred.set_current_cloud_accounts([])  # builds {} -> fail-closed signal
    try:
        with pytest.raises(RuntimeError, match="no AWS account connected"):
            cred.resolve_session()
    finally:
        cred.reset_current_cloud_account(token)


def test_bash_aws_blocked_on_explicit_empty_accounts(monkeypatch):
    """Mirror of the resolver test at the bash layer: with {} on the contextvar, bash `aws`
    is denied without touching subprocess (so the platform's `aws` CLI can't be used either)."""
    from opendevops_core.tools import bash_tool

    def _no_run(*a, **k):  # subprocess must not execute
        raise AssertionError("subprocess.run must not run when accounts is explicitly empty")

    monkeypatch.setattr(bash_tool.subprocess, "run", _no_run)
    token = cred.set_current_cloud_accounts([])
    try:
        res = bash_tool.run_bash_command("aws sts get-caller-identity")
    finally:
        cred.reset_current_cloud_account(token)

    assert res["success"] is False and res.get("blocked") is True
    assert "no cloud account" in res["error"].lower()
