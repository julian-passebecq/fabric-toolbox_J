import pytest

from app.catalog import combined_catalog
from app.models import MutationArtifactRequest, SessionStatus
import app.mutations as mutation_module
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



def test_guarded_eventhouse_create_uses_whatif_and_name_readback(monkeypatch):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())
    seen = {}

    def validate(capability, parameters):
        seen["validate"] = (capability.command, dict(parameters))
        return {"success": True, "mode": "what-if"}

    def execute(capability, parameters):
        seen["execute"] = (capability.command, dict(parameters))
        return {"id": "eventhouse-1", "displayName": parameters["EventhouseName"]}

    def read(capability, parameters):
        seen["read"] = (capability.command, dict(parameters))
        return {"id": "eventhouse-1", "displayName": parameters["EventhouseName"]}

    monkeypatch.setattr(runtime, "validate_guarded_write", validate)
    monkeypatch.setattr(runtime, "execute_guarded_write", execute)
    monkeypatch.setattr(runtime, "execute_read", read)

    create = next(item for item in combined_catalog() if item.command == "New-FabricEventhouse")
    plan = broker.create_plan(
        create,
        {"WorkspaceId": "ws-1", "EventhouseName": "foilo_rti"},
    )

    validation = broker.validate(plan.plan_id)
    result = broker.execute(plan.plan_id, validation.plan.confirmation_text)

    assert seen["validate"][0] == "New-FabricEventhouse"
    assert seen["execute"][0] == "New-FabricEventhouse"
    assert seen["read"] == (
        "Get-FabricEventhouse",
        {"WorkspaceId": "ws-1", "EventhouseName": "foilo_rti"},
    )
    assert result.verification["id"] == "eventhouse-1"


def test_guarded_item_create_cannot_plan_without_mandatory_fields(monkeypatch):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())
    create = next(item for item in combined_catalog() if item.command == "New-FabricEventstream")

    with pytest.raises(ValueError, match="EventstreamName"):
        broker.create_plan(create, {"WorkspaceId": "ws-1"})


def test_guarded_kql_database_plan_preserves_parent_eventhouse_binding(monkeypatch):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())

    create = next(item for item in combined_catalog() if item.command == "New-FabricKQLDatabase")
    plan = broker.create_plan(
        create,
        {
            "WorkspaceId": "ws-1",
            "KQLDatabaseName": "wind_telemetry",
            "KQLDatabaseType": "ReadWrite",
            "parentEventhouseId": "eventhouse-1",
        },
    )

    assert plan.supports_validation is True
    assert "-parentEventhouseId 'eventhouse-1'" in plan.rendered_command
    assert "-KQLDatabaseType 'ReadWrite'" in plan.rendered_command
    assert "-WhatIf" in (plan.validation_command or "")


def test_bound_eventstream_artifact_is_hash_verified_before_whatif(monkeypatch, tmp_path):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())
    monkeypatch.setattr(mutation_module, "ARTIFACT_ROOT", tmp_path)

    create = next(item for item in combined_catalog() if item.command == "New-FabricEventstream")
    plan = broker.create_plan(
        create,
        {"WorkspaceId": "ws-1", "EventstreamName": "wind_events"},
        artifacts=[
            MutationArtifactRequest(
                parameter="EventstreamPathDefinition",
                filename="eventstream.json",
                content='{"sources":[],"destinations":[],"streams":[],"operators":[],"compatibilityLevel":"1.1"}',
            )
        ],
    )

    assert len(plan.artifacts) == 1
    artifact = plan.artifacts[0]
    assert artifact.parameter == "EventstreamPathDefinition"
    assert len(artifact.sha256) == 64
    bound_path = plan.parameters["EventstreamPathDefinition"]
    assert "eventstream.json" in str(bound_path)
    assert "-EventstreamPathDefinition" in plan.rendered_command

    with open(bound_path, "w", encoding="utf-8") as handle:
        handle.write('{"tampered":true}')

    with pytest.raises(UnsafeOperation, match="changed after approval"):
        broker.validate(plan.plan_id)


def test_bound_eventstream_artifact_survives_whatif_then_cleans_up(monkeypatch, tmp_path):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())
    monkeypatch.setattr(mutation_module, "ARTIFACT_ROOT", tmp_path)

    seen = {}

    def validate(capability, parameters):
        seen["validate_path"] = parameters["EventstreamPathDefinition"]
        return {"success": True, "mode": "what-if"}

    def execute(capability, parameters):
        seen["execute_path"] = parameters["EventstreamPathDefinition"]
        return {"id": "eventstream-1", "displayName": parameters["EventstreamName"]}

    monkeypatch.setattr(runtime, "validate_guarded_write", validate)
    monkeypatch.setattr(runtime, "execute_guarded_write", execute)
    monkeypatch.setattr(
        runtime,
        "execute_read",
        lambda capability, parameters: {"id": "eventstream-1", "displayName": "wind_events"},
    )

    create = next(item for item in combined_catalog() if item.command == "New-FabricEventstream")
    plan = broker.create_plan(
        create,
        {"WorkspaceId": "ws-1", "EventstreamName": "wind_events"},
        artifacts=[
            MutationArtifactRequest(
                parameter="EventstreamPathDefinition",
                filename="eventstream.json",
                content='{"sources":[],"destinations":[],"streams":[],"operators":[],"compatibilityLevel":"1.1"}',
            )
        ],
    )
    bound_path = plan.parameters["EventstreamPathDefinition"]

    validation = broker.validate(plan.plan_id)
    assert validation.plan.status == "validated"
    assert seen["validate_path"] == bound_path

    result = broker.execute(plan.plan_id, validation.plan.confirmation_text)
    assert result.plan.status == "executed"
    assert seen["execute_path"] == bound_path
    assert not (tmp_path / plan.plan_id).exists()


def test_artifact_binding_rejects_non_definition_parameter(monkeypatch, tmp_path):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())
    monkeypatch.setattr(mutation_module, "ARTIFACT_ROOT", tmp_path)

    create = next(item for item in combined_catalog() if item.command == "New-FabricEventstream")
    with pytest.raises(UnsafeOperation, match="not allowed"):
        broker.create_plan(
            create,
            {"WorkspaceId": "ws-1", "EventstreamName": "wind_events"},
            artifacts=[
                MutationArtifactRequest(
                    parameter="EventstreamDescription",
                    filename="description.txt",
                    content="not a definition file",
                )
            ],
        )


def test_artifact_binding_rejects_path_traversal_filename(monkeypatch, tmp_path):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())
    monkeypatch.setattr(mutation_module, "ARTIFACT_ROOT", tmp_path)

    create = next(item for item in combined_catalog() if item.command == "New-FabricEventstream")
    with pytest.raises(ValueError, match="plain file name"):
        broker.create_plan(
            create,
            {"WorkspaceId": "ws-1", "EventstreamName": "wind_events"},
            artifacts=[
                MutationArtifactRequest(
                    parameter="EventstreamPathDefinition",
                    filename="../eventstream.json",
                    content="{}",
                )
            ],
        )


def test_guarded_eventstream_definition_update_binds_artifact_and_reads_back(monkeypatch, tmp_path):
    broker = MutationBroker()
    monkeypatch.setattr(runtime, "status", lambda: _connected())
    monkeypatch.setattr(mutation_module, "ARTIFACT_ROOT", tmp_path)

    seen = {}

    def validate(capability, parameters):
        seen["validate"] = (capability.command, dict(parameters))
        return {"success": True, "mode": "what-if"}

    def execute(capability, parameters):
        seen["execute"] = (capability.command, dict(parameters))
        return {"success": True}

    def read(capability, parameters):
        seen["read"] = (capability.command, dict(parameters))
        return {"definition": {"parts": [{"path": "eventstream.json"}]}}

    monkeypatch.setattr(runtime, "validate_guarded_write", validate)
    monkeypatch.setattr(runtime, "execute_guarded_write", execute)
    monkeypatch.setattr(runtime, "execute_read", read)

    update = next(item for item in combined_catalog() if item.command == "Update-FabricEventstreamDefinition")
    plan = broker.create_plan(
        update,
        {"WorkspaceId": "ws-1", "EventstreamId": "eventstream-1"},
        artifacts=[
            MutationArtifactRequest(
                parameter="EventstreamPathDefinition",
                filename="eventstream.json",
                content='{"sources":[],"destinations":[],"streams":[],"operators":[],"compatibilityLevel":"1.1"}',
            )
        ],
    )

    assert plan.artifacts[0].parameter == "EventstreamPathDefinition"
    validation = broker.validate(plan.plan_id)
    result = broker.execute(plan.plan_id, validation.plan.confirmation_text)

    assert seen["validate"][0] == "Update-FabricEventstreamDefinition"
    assert seen["execute"][0] == "Update-FabricEventstreamDefinition"
    assert seen["read"] == (
        "Get-FabricEventstreamDefinition",
        {"WorkspaceId": "ws-1", "EventstreamId": "eventstream-1"},
    )
    assert result.verification["definition"]["parts"][0]["path"] == "eventstream.json"
    assert not (tmp_path / plan.plan_id).exists()
