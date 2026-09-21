import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.models import SessionStatus
from app.project_contract import load_manifest


STUDIO_ROOT = Path(__file__).resolve().parents[2]
PROJECT = STUDIO_ROOT / "examples" / "fabric-project" / "foil.project.json"


class RuntimeStub:
    def __init__(self):
        self._status = SessionStatus()

    def status(self):
        return self._status


def test_project_readiness_route_is_offline_and_non_executing(monkeypatch):
    runtime = RuntimeStub()
    monkeypatch.setattr(main, "runtime", runtime)
    monkeypatch.setenv("STUDIO_CLIENT_TOKEN", "fixture-client")
    project = load_manifest(PROJECT)

    with TestClient(
        main.app,
        base_url="http://127.0.0.1:8765",
        headers={"X-Studio-Client": "fixture-client"},
    ) as client:
        response = client.post("/api/project/readiness", json={"project": project, "profile_name": "dev"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["authorization"] is False
    assert payload["deployable"] is False
    assert all(action["executable"] is False for action in payload["bootstrap_actions"])
    checks = {check["id"]: check for check in payload["checks"]}
    assert checks["workspace.target"]["status"] == "unknown"


def test_project_readiness_route_rejects_unknown_profile(monkeypatch):
    monkeypatch.setattr(main, "runtime", RuntimeStub())
    monkeypatch.setenv("STUDIO_CLIENT_TOKEN", "fixture-client")
    project = load_manifest(PROJECT)

    with TestClient(
        main.app,
        base_url="http://127.0.0.1:8765",
        headers={"X-Studio-Client": "fixture-client"},
    ) as client:
        response = client.post("/api/project/readiness", json={"project": project, "profile_name": "missing"})

    assert response.status_code == 400
    assert "profile.unknown" in response.json()["detail"]
