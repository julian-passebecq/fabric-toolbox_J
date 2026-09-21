from __future__ import annotations

import socket

import pytest

from app.models import SessionStatus
from app.project_contract import ProjectContractError, load_manifest
from app.readiness import evaluate_project_readiness

from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parents[2]
PROJECT = STUDIO_ROOT / "examples" / "fabric-project" / "foil.project.json"


def manifest():
    return load_manifest(PROJECT)


def test_disconnected_readiness_is_conservative_and_never_authorizes_deploy():
    report = evaluate_project_readiness(manifest(), "dev", SessionStatus())
    checks = {check.id: check for check in report.checks}
    assert report.deployable is False
    assert report.authorization is False
    assert checks["project.contract"].status == "satisfied"
    assert checks["identity.fabric-session"].status == "action_required"
    assert checks["workspace.target"].status == "unknown"
    assert all(action.executable is False for action in report.bootstrap_actions)
    assert any(action.id == "observe-workspace" for action in report.bootstrap_actions)


def test_connected_session_does_not_turn_unobserved_runtime_state_green():
    session = SessionStatus(connected=True, tenant_id="tenant-a", generation="g")
    report = evaluate_project_readiness(manifest(), "dev", session)
    checks = {check.id: check for check in report.checks}
    assert checks["identity.fabric-session"].status == "satisfied"
    assert checks["identity.fabric-session"].evidence_kind == "backend-session"
    assert checks["workspace.target"].status == "unknown"
    assert checks["support.eventhouse"].status == "unknown"
    assert report.counts["unknown"] > 0
    assert report.deployable is False


def test_readiness_rejects_invalid_or_unknown_project_profile():
    project = manifest()
    project["resources"][0]["dependsOn"] = ["missing"]
    with pytest.raises(ProjectContractError):
        evaluate_project_readiness(project, "dev", SessionStatus())
    with pytest.raises(ProjectContractError):
        evaluate_project_readiness(manifest(), "missing", SessionStatus())


def test_readiness_is_offline_and_does_not_open_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("readiness evaluation attempted network access")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    report = evaluate_project_readiness(manifest(), "prod", SessionStatus())
    assert report.project_id == "foil"


def test_telemetry_secret_is_reference_only_and_availability_stays_unknown():
    report = evaluate_project_readiness(manifest(), "dev", SessionStatus())
    checks = {check.id: check for check in report.checks}
    assert checks["telemetry.connection-reference"].status == "satisfied"
    assert "secretref:" in checks["telemetry.connection-reference"].detail
    assert checks["telemetry.connection-availability"].status == "unknown"
