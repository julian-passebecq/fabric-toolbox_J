import pytest
from app import activity, admission
from app.providers.microsoftfabricmgmt import runtime


@pytest.fixture(autouse=True)
def isolated_activity(tmp_path, monkeypatch):
    monkeypatch.setattr(activity,'ACTIVITY_FILE',tmp_path/'activity.jsonl')
    # Exercise the candidate broker only with mocks/harmless fixtures. Production
    # remains suspended pending the lead's upstream retry/204 decision.
    monkeypatch.setattr(admission,'WRITE_ADMISSION_SUSPENDED',False)
    # Legacy broker unit tests explicitly replace provider calls. No global runtime
    # may start PowerShell accidentally; real transport fixtures use new instances.
    def denied():raise AssertionError('Unexpected real provider initialization in a unit test')
    monkeypatch.setattr(runtime,'_load_session_type',denied)
    monkeypatch.setattr(runtime,'bind_artifact',lambda expected:'fixture-artifact')
    monkeypatch.setattr(runtime,'artifact_fingerprint',lambda:'fixture-artifact')
