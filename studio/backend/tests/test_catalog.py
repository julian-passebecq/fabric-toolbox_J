import pytest

from app.catalog import combined_catalog, discover_powershell_capabilities
from app.providers.fabric_rest import build_rest_get_command
from app.providers.microsoftfabricmgmt import (
    UnsafeOperation,
    build_guarded_write_command,
    build_read_command,
)


def test_discovers_workspace_command():
    capabilities = discover_powershell_capabilities()
    workspace = next(item for item in capabilities if item.command == "Get-FabricWorkspace")

    assert workspace.category == "Workspace"
    assert workspace.risk == "read"
    assert workspace.execution_policy == "read"
    assert workspace.source_path.endswith("Get-FabricWorkspace.ps1")
    assert "WorkspaceId" in workspace.parameters
    assert "WorkspaceName" in workspace.parameters
    assert "workspace" in workspace.description.lower()

    specs = {spec.name: spec for spec in workspace.parameter_specs}
    assert specs["WorkspaceId"].type.lower() == "string"
    assert specs["WorkspaceId"].mandatory is False
    assert specs["Raw"].is_switch is True
    assert specs["Raw"].type.lower() == "switch"


def test_classifies_remove_as_destructive_and_blocks_it():
    capabilities = discover_powershell_capabilities()
    remove_workspace = next(item for item in capabilities if item.command == "Remove-FabricWorkspace")
    assert remove_workspace.risk == "destructive"
    assert remove_workspace.execution_policy == "blocked"


def test_curated_entries_overlay_generated_metadata():
    catalog = combined_catalog()
    workspace = next(item for item in catalog if item.id == "ps-workspace-get-fabricworkspace")

    assert workspace.title == "List workspaces"
    assert workspace.generated is False
    assert workspace.provider == "MicrosoftFabricMgmt"
    assert workspace.execution_policy == "read"
    assert "WorkspaceId" in workspace.parameters
    assert any(spec.name == "Raw" and spec.is_switch for spec in workspace.parameter_specs)
    assert workspace.source_path.endswith("Get-FabricWorkspace.ps1")


def test_workspace_roles_remain_upstream_discovered():
    roles = next(item for item in combined_catalog() if item.id == "ps-workspace-get-fabricworkspaceroleassignment")
    assert roles.command == "Get-FabricWorkspaceRoleAssignment"
    assert roles.provider == "MicrosoftFabricMgmt"
    assert roles.generated is False
    assert roles.execution_policy == "read"
    assert roles.parameters


def test_only_curated_workspace_writes_are_guarded():
    catalog = combined_catalog()
    create_workspace = next(item for item in catalog if item.id == "ps-workspace-new-fabricworkspace")
    update_workspace = next(item for item in catalog if item.id == "ps-workspace-update-fabricworkspace")
    add_role = next(item for item in catalog if item.command == "Add-FabricWorkspaceRoleAssignment")

    assert create_workspace.risk == "write"
    assert create_workspace.execution_policy == "guarded-write"
    assert create_workspace.supports_whatif is True
    assert create_workspace.verification_capability_id == "ps-workspace-get-fabricworkspace"

    assert update_workspace.risk == "write"
    assert update_workspace.execution_policy == "guarded-write"
    assert update_workspace.supports_whatif is True
    assert update_workspace.verification_parameter_map == {"WorkspaceId": "WorkspaceId"}

    assert add_role.risk == "write"
    assert add_role.execution_policy == "blocked"


def test_builds_safe_read_command():
    workspace = next(item for item in discover_powershell_capabilities() if item.command == "Get-FabricWorkspace")
    command = build_read_command(workspace, {"WorkspaceName": "Finance O'Brien"})

    assert "Get-FabricWorkspace" in command
    assert "-WorkspaceName 'Finance O''Brien'" in command
    assert "ConvertTo-Json" in command


def test_builds_switch_parameter_without_value():
    workspace = next(item for item in discover_powershell_capabilities() if item.command == "Get-FabricWorkspace")
    command = build_read_command(workspace, {"Raw": True})
    assert "-Raw" in command
    assert "-Raw True" not in command


def test_rejects_unknown_parameter():
    workspace = next(item for item in discover_powershell_capabilities() if item.command == "Get-FabricWorkspace")
    with pytest.raises(ValueError):
        build_read_command(workspace, {"NotAParameter": "x"})


def test_rejects_mutating_command_on_read_executor():
    remove_workspace = next(item for item in discover_powershell_capabilities() if item.command == "Remove-FabricWorkspace")
    with pytest.raises(UnsafeOperation):
        build_read_command(remove_workspace, {"WorkspaceId": "abc"})


def test_guarded_workspace_create_renders_exact_command_and_whatif():
    create_workspace = next(item for item in combined_catalog() if item.id == "ps-workspace-new-fabricworkspace")
    command = build_guarded_write_command(
        create_workspace,
        {"WorkspaceName": "Finance Lab", "WorkspaceDescription": "Sandbox"},
    )
    what_if = build_guarded_write_command(
        create_workspace,
        {"WorkspaceName": "Finance Lab", "WorkspaceDescription": "Sandbox"},
        what_if=True,
    )

    assert "New-FabricWorkspace" in command
    assert "-WorkspaceName 'Finance Lab'" in command
    assert "-WorkspaceDescription 'Sandbox'" in command
    assert "-WhatIf" not in command
    assert "-WhatIf" in what_if
    assert "mode = 'what-if'" in what_if


def test_guarded_write_builder_rejects_non_allowlisted_write():
    add_role = next(item for item in combined_catalog() if item.command == "Add-FabricWorkspaceRoleAssignment")
    with pytest.raises(UnsafeOperation, match="allowlisted"):
        build_guarded_write_command(
            add_role,
            {
                "WorkspaceId": "ws",
                "PrincipalId": "principal",
                "PrincipalType": "User",
                "WorkspaceRole": "Viewer",
            },
        )


def test_builds_registered_items_rest_get_via_upstream_module():
    items = next(item for item in combined_catalog() if item.id == "rest-items-list")
    command = build_rest_get_command(items, {"workspaceId": "ws-123", "type": "Notebook"})

    assert "Invoke-FabricAuthCheck" in command
    assert "$script:FabricAuthContext.FabricHeaders" in command
    assert "Invoke-FabricAPIRequest" in command
    assert "-Method 'Get'" in command
    assert "-WaitForCompletion" not in command
    assert "https://api.fabric.microsoft.com/v1/workspaces/ws-123/items?type=Notebook" in command


def test_registered_item_detail_and_connections_endpoints():
    catalog = combined_catalog()
    detail = next(item for item in catalog if item.id == "rest-item-get")
    connections = next(item for item in catalog if item.id == "rest-item-connections-list")

    detail_command = build_rest_get_command(
        detail,
        {"workspaceId": "ws", "itemId": "item", "include": "DefaultIdentity"},
    )
    connection_command = build_rest_get_command(connections, {"workspaceId": "ws", "itemId": "item"})

    assert "/v1/workspaces/ws/items/item?include=DefaultIdentity" in detail_command
    assert "/v1/workspaces/ws/items/item/connections" in connection_command


def test_git_status_uses_upstream_lro_waiting():
    git_status = next(item for item in combined_catalog() if item.id == "rest-git-status")
    command = build_rest_get_command(git_status, {"workspaceId": "ws-123"})

    assert git_status.response_mode == "fabric-lro"
    assert "/v1/workspaces/ws-123/git/status" in command
    assert "Invoke-FabricAPIRequest" in command
    assert "-WaitForCompletion" in command


def test_rest_path_and_query_values_are_url_encoded():
    items = next(item for item in combined_catalog() if item.id == "rest-items-list")
    command = build_rest_get_command(items, {"workspaceId": "a b", "type": "Data Pipeline"})

    assert "/workspaces/a%20b/items?type=Data+Pipeline" in command


def test_rest_requires_registered_mandatory_parameters():
    items = next(item for item in combined_catalog() if item.id == "rest-items-list")
    with pytest.raises(ValueError, match="workspaceId"):
        build_rest_get_command(items, {})


def test_rest_rejects_unknown_parameters():
    items = next(item for item in combined_catalog() if item.id == "rest-items-list")
    with pytest.raises(ValueError, match="Unknown parameters"):
        build_rest_get_command(items, {"workspaceId": "ws", "arbitraryUrl": "https://example.com"})


def test_rest_blocks_registered_write_endpoint():
    create_db = next(item for item in combined_catalog() if item.id == "rest-sqldatabase-create")
    with pytest.raises(UnsafeOperation):
        build_rest_get_command(create_db, {"workspaceId": "ws"})
