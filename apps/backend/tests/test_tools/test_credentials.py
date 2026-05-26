"""Per-org AWS credential resolution + cache isolation."""

from moto import mock_aws
from opendevops_core.providers.aws import credentials as cred
from opendevops_core.tools._cache import tool_cached


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
