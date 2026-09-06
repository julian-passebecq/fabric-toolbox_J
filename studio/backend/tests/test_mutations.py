import pytest

from app.catalog import combined_catalog
from app.models import SessionStatus
from app.mutations import MutationBroker
from app.providers.microsoftfabricmgmt import UnsafeOperation, runtime


def _workspace_create():
    return next(item for item in combined_catalog() if item.id == "ps-workspace-new-fabricworkspace")


def _workspace_update():
    return next(item for item in combined_catalog() if item.id == "ps-workspace-update-fabricworkspace")


def _connected(tenant_id="tenant-a"):
    return SessionStatus(connected=True, tenant_id=tenant_id)


def test_plan_is_tenant_bound_digest_bound_and_expiring(monkeypatch):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())

    plan = broker.create_plan(_workspace_create(), {"WorkspaceName": "Finance Lab"})

    assert plan.status == "planned"
    assert plan.tenant_id == "tenant-a"
    assert plan.supports_validation is True
    assert "New-FabricWorkspace" in plan.rendered_command
    assert "-WhatIf" in (plan.validation_command or "")
    assert plan.confirmation_text.startswith("APPLY ")
    assert len(plan.digest) == 64
    assert plan.expires_at > plan.created_at


def test_whatif_is_required_before_execution(monkeypatch):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())
    monkeypatch.setattr(runtime, "validate_guarded_write", lambda capability, parameters: {"success": True, "output": "What if"})
    monkeypatch.setattr(runtime, "execute_guarded_write", lambda capability, parameters: {"id": "workspace-1"})
    monkeypatch.setattr(runtime, "execute_read", lambda capability, parameters: {"id": "workspace-1", "displayName": "Finance Lab"})

    plan = broker.create_plan(_workspace_create(), {"WorkspaceName": "Finance Lab"})

    with pytest.raises(UnsafeOperation, match="WhatIf"):
        broker.execute(plan.plan_id, plan.confirmation_text)

    validation = broker.validate(plan.plan_id)
    assert validation.plan.status == "validated"
    assert validation.result["success"] is True

    with pytest.raises(UnsafeOperation, match="Confirmation"):
        broker.execute(plan.plan_id, "APPLY WRONG")

    result = broker.execute(plan.plan_id, plan.confirmation_text)
    assert result.plan.status == "executed"
    assert result.result["id"] == "workspace-1"
    assert result.verification["displayName"] == "Finance Lab"

    with pytest.raises(UnsafeOperation, match="status executed"):
        broker.execute(plan.plan_id, plan.confirmation_text)


def test_plan_cannot_cross_tenant_sessions(monkeypatch):
    broker = MutationBroker()
    current = {"tenant": "tenant-a"}
    monkeypatch.setattr(runtime, "status", lambda: _connected(current["tenant"]))
    monkeypatch.setattr(runtime, "validate_guarded_write", lambda capability, parameters: {"success": True})

    plan = broker.create_plan(_workspace_create(), {"WorkspaceName": "Finance Lab"})
    current["tenant"] = "tenant-b"

    with pytest.raises(UnsafeOperation, match="different Fabric tenant"):
        broker.validate(plan.plan_id)


def test_workspace_update_requires_name_or_description(monkeypatch):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())

    with pytest.raises(ValueError, match="WorkspaceName, WorkspaceDescription"):
        broker.create_plan(_workspace_update(), {"WorkspaceId": "ws-1"})

    plan = broker.create_plan(
        _workspace_update(),
        {"WorkspaceId": "ws-1", "WorkspaceDescription": "New description"},
    )
    assert "Update-FabricWorkspace" in plan.rendered_command
    assert "-WorkspaceDescription 'New description'" in plan.rendered_command


def test_non_allowlisted_write_cannot_create_plan(monkeypatch):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())
    add_role = next(item for item in combined_catalog() if item.command == "Add-FabricWorkspaceRoleAssignment")

    with pytest.raises(UnsafeOperation, match="allowlisted"):
        broker.create_plan(
            add_role,
            {
                "WorkspaceId": "ws",
                "PrincipalId": "principal",
                "PrincipalType": "User",
                "WorkspaceRole": "Viewer",
            },
        )
