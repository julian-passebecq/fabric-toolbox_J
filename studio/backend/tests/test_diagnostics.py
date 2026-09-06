from app.diagnostics import collect_diagnostics
from app.specialized_tools import list_specialized_tools


def test_diagnostics_returns_runtime_and_catalog_shape():
    diagnostics = collect_diagnostics()

    assert diagnostics["status"] in {"ready", "degraded"}
    assert isinstance(diagnostics["catalog"]["total"], int)
    assert diagnostics["catalog"]["total"] > 0
    assert "MicrosoftFabricMgmt" in diagnostics["catalog"]["providers"]
    assert "read" in diagnostics["catalog"]["risks"]
    assert diagnostics["session"]["mode"] == "read-only"
    assert isinstance(diagnostics["session"]["connected"], bool)
    assert diagnostics["checks"]
    assert all({"name", "ok", "required", "detail"}.issubset(check) for check in diagnostics["checks"])


def test_specialized_tools_are_explicit_and_upstream_backed():
    tools = {tool["id"]: tool for tool in list_specialized_tools()}

    assert set(tools) == {
        "fabric-security-audit",
        "fabric-assessment-tool",
        "lineage-extractor",
    }
    assert tools["fabric-security-audit"]["available"] is True
    assert tools["fabric-security-audit"]["entrypoint"].endswith("Invoke-FabricSecurityAudit.ps1")
    assert tools["fabric-assessment-tool"]["available"] is True
    assert tools["fabric-assessment-tool"]["entrypoint"] == "fat assess"
    assert tools["lineage-extractor"]["available"] is True
    assert tools["lineage-extractor"]["execution_kind"] == "fabric-notebook"


def test_specialized_tools_are_not_generic_read_operations():
    for tool in list_specialized_tools():
        assert tool["status"] in {"preview-only", "external-notebook"}
        assert tool["risk"] == "admin"
        assert tool["reason"]
        assert tool["prerequisites"]
