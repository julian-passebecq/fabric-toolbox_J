from app.catalog import combined_catalog, discover_powershell_capabilities


def test_discovers_workspace_command():
    capabilities = discover_powershell_capabilities()
    workspace = next(item for item in capabilities if item.command == "Get-FabricWorkspace")

    assert workspace.category == "Workspace"
    assert workspace.risk == "read"
    assert workspace.source_path.endswith("Get-FabricWorkspace.ps1")
    assert "WorkspaceId" in workspace.parameters
    assert "WorkspaceName" in workspace.parameters


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
