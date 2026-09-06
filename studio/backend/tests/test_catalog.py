import pytest

from app.catalog import combined_catalog, discover_powershell_capabilities
from app.providers.microsoftfabricmgmt import UnsafeOperation, build_read_command


def test_discovers_workspace_command():
    capabilities = discover_powershell_capabilities()
    workspace = next(item for item in capabilities if item.command == "Get-FabricWorkspace")

    assert workspace.category == "Workspace"
    assert workspace.risk == "read"
    assert workspace.source_path.endswith("Get-FabricWorkspace.ps1")
    assert "WorkspaceId" in workspace.parameters
    assert "WorkspaceName" in workspace.parameters
    assert "workspace" in workspace.description.lower()

    specs = {spec.name: spec for spec in workspace.parameter_specs}
    assert specs["WorkspaceId"].type.lower() == "string"
    assert specs["WorkspaceId"].mandatory is False
    assert specs["Raw"].is_switch is True
    assert specs["Raw"].type.lower() == "switch"


def test_classifies_remove_as_destructive():
    capabilities = discover_powershell_capabilities()
    remove_workspace = next(item for item in capabilities if item.command == "Remove-FabricWorkspace")
    assert remove_workspace.risk == "destructive"


def test_curated_entries_overlay_generated_metadata():
    catalog = combined_catalog()
    workspace = next(item for item in catalog if item.id == "ps-workspace-get-fabricworkspace")

    assert workspace.title == "List workspaces"
    assert workspace.generated is False
    assert workspace.provider == "MicrosoftFabricMgmt"
    assert "WorkspaceId" in workspace.parameters
    assert any(spec.name == "Raw" and spec.is_switch for spec in workspace.parameter_specs)
    assert workspace.source_path.endswith("Get-FabricWorkspace.ps1")


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


def test_rejects_mutating_command():
    remove_workspace = next(item for item in discover_powershell_capabilities() if item.command == "Remove-FabricWorkspace")
    with pytest.raises(UnsafeOperation):
        build_read_command(remove_workspace, {"WorkspaceId": "abc"})
