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


def test_classifies_remove_as_destructive():
    capabilities = discover_powershell_capabilities()
    remove_workspace = next(item for item in capabilities if item.command == "Remove-FabricWorkspace")
    assert remove_workspace.risk == "destructive"


def test_curated_entries_override_generated_entries():
    catalog = combined_catalog()
    workspace = next(item for item in catalog if item.id == "ps-workspace-get-fabricworkspace")

    assert workspace.title == "List workspaces"
    assert workspace.generated is False
    assert workspace.provider == "MicrosoftFabricMgmt"


def test_builds_safe_read_command():
    workspace = next(item for item in discover_powershell_capabilities() if item.command == "Get-FabricWorkspace")
    command = build_read_command(workspace, {"WorkspaceName": "Finance O'Brien"})

    assert "Get-FabricWorkspace" in command
    assert "-WorkspaceName 'Finance O''Brien'" in command
    assert "ConvertTo-Json" in command


def test_rejects_unknown_parameter():
    workspace = next(item for item in discover_powershell_capabilities() if item.command == "Get-FabricWorkspace")
    with pytest.raises(ValueError):
        build_read_command(workspace, {"NotAParameter": "x"})


def test_rejects_mutating_command():
    remove_workspace = next(item for item in discover_powershell_capabilities() if item.command == "Remove-FabricWorkspace")
    with pytest.raises(UnsafeOperation):
        build_read_command(remove_workspace, {"WorkspaceId": "abc"})
