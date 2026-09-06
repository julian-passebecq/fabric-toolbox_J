from app.diagnostics import _compatibility_report, collect_diagnostics
from app.models import Capability
from app.specialized_tools import list_specialized_tools


def test_diagnostics_returns_runtime_catalog_and_compatibility_shape():
    diagnostics = collect_diagnostics()

    assert diagnostics["status"] in {"ready", "degraded"}
    assert isinstance(diagnostics["catalog"]["total"], int)
    assert diagnostics["catalog"]["total"] > 0
    assert "MicrosoftFabricMgmt" in diagnostics["catalog"]["providers"]
    assert "read" in diagnostics["catalog"]["risks"]
    assert diagnostics["session"]["mode"] == "guarded-writes"
    assert isinstance(diagnostics["session"]["connected"], bool)
    assert diagnostics["checks"]
    assert all({"name", "ok", "required", "detail"}.issubset(check) for check in diagnostics["checks"])

    compatibility = diagnostics["compatibility"]
    assert compatibility["status"] in {"compatible", "incompatible"}
    assert isinstance(compatibility["errors"], int)
    assert isinstance(compatibility["warnings"], int)
    assert isinstance(compatibility["issues"], list)


def test_compatibility_report_detects_duplicate_ids_and_broken_verification():
    catalog = [
        Capability(
            id="duplicate",
            title="A",
            category="Test",
            provider="MicrosoftFabricMgmt",
            source="test",
            risk="read",
            command="Get-A",
            verification_capability_id="missing-readback",
        ),
        Capability(
            id="duplicate",
            title="B",
            category="Test",
            provider="Fabric REST API",
            source="test",
            risk="read",
            endpoint="not-v1",
        ),
    ]

    report = _compatibility_report(catalog)
    assert report["status"] == "incompatible"
    assert "duplicate" in report["duplicate_ids"]
    messages = " ".join(issue["message"] for issue in report["issues"])
    assert "duplicated" in messages
    assert "Verification capability" in messages
    assert "/v1/ endpoint" in messages


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
