"""Tests for the AWS permission probe — its declarative table drives both the live
check and the published inventory, so they cannot drift."""

from __future__ import annotations


def test_check_permissions_runs_every_probe(mocker):
    """check_permissions iterates PERMISSION_PROBES: one keyed result per probe, each
    invoking its declared boto3 operation."""
    from opendevops_core.providers.aws import permissions

    client = mocker.MagicMock()
    session = mocker.MagicMock()
    session.client.return_value = client
    mocker.patch.object(permissions, "_session", return_value=session)
    mocker.patch.object(permissions, "resolve_region", return_value="us-east-1")

    results = permissions.check_permissions()

    assert set(results) == {label for label, _, _, _ in permissions.PERMISSION_PROBES}
    assert all(r["passed"] for r in results.values())
    # Each probe's declared operation was actually called on its boto3 client.
    called = {c[0] for c in client.method_calls}
    assert {op for _, _, op, _ in permissions.PERMISSION_PROBES} <= called
