"""Safety acceptance for the repaired workspace-write transport contract.

The previous S01 fixture documented that MaxRetries=0 still replayed 503/504 four
times and that HTTP 204 was treated as failure. These tests close that reproduced
defect while production write admission remains suspended pending live DEV evidence.
"""
import json
import subprocess
from pathlib import Path

import pytest

from app import admission
from app.catalog import combined_catalog
from app.providers.microsoftfabricmgmt import build_guarded_write_command, UnsafeOperation
from app.providers.outcomes import InvocationFailure, OutcomeUnknown, normalize


HELPER = Path("tools/MicrosoftFabricMgmt/source/Public/Utils/Invoke-FabricAPIRequest.ps1")


def _transport_fixture(status: int | None, *, single_dispatch=True, max_retries=0, network_error=False):
    flags = []
    if max_retries is not None:
        flags.append(f"-MaxRetries {max_retries}")
    if single_dispatch:
        flags.append("-SingleDispatch")
    flags.append("-ReturnTransportOutcome")
    script = r"""
$script:calls=0
function Write-FabricLog {}
function Get-PSFConfigValue { param($FullName,$Fallback); return $Fallback }
function Get-FabricRetryDelay { return 0 }
function Start-Sleep {}
function Invoke-RestMethod {
    param($Headers,$Uri,$Method,$Body,$ContentType,$ErrorAction,[switch]$SkipHttpErrorCheck,$StatusCodeVariable,$ResponseHeadersVariable)
    $script:calls++
    if (NETWORK_ERROR) { throw [System.Net.Http.HttpRequestException]::new('fixture connection loss') }
    Set-Variable -Scope 1 -Name $StatusCodeVariable -Value STATUS
    Set-Variable -Scope 1 -Name $ResponseHeadersVariable -Value @{
        'x-ms-request-id'='corr-123'
        'x-ms-operation-id'='op-456'
        'Retry-After'='2'
        'Authorization'='secret-must-not-leak'
    }
    return [PSCustomObject]@{id='workspace-1';requestId='body-request-id';message='fixture HTTP response';secret='body-secret-must-not-leak'}
}
. './tools/MicrosoftFabricMgmt/source/Public/Utils/Invoke-FabricAPIRequest.ps1'
$result = Invoke-FabricAPIRequest -Headers @{fixture='value'} -BaseURI 'https://unused.invalid' -Method Post FLAGS
@{calls=$script:calls;result=$result} | ConvertTo-Json -Depth 10 -Compress
"""
    script = script.replace("NETWORK_ERROR", "$true" if network_error else "$false")
    script = script.replace("STATUS", "$null" if status is None else str(status))
    script = script.replace("FLAGS", " ".join(flags))
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    assert "secret-must-not-leak" not in result.stdout
    assert "body-secret-must-not-leak" not in result.stdout
    return json.loads(result.stdout)


@pytest.mark.parametrize("status,state", [
    (200, "succeeded"),
    (201, "succeeded"),
    (202, "accepted"),
    (204, "succeeded"),
    (400, "failed"),
    (403, "failed"),
    (429, "failed"),
    (503, "outcome_unknown"),
    (504, "outcome_unknown"),
])
def test_single_dispatch_transport_matrix(status, state):
    evidence = _transport_fixture(status)
    assert evidence["calls"] == 1
    outcome = evidence["result"]
    assert outcome["studio_transport_outcome"] == 1
    assert outcome["state"] == state
    assert outcome["statusCode"] == status
    assert outcome["dispatchCount"] == 1
    assert outcome["correlationId"] == "corr-123"
    if status in {200, 201}:
        assert outcome["id"] == "workspace-1"
    if status == 202:
        assert outcome["operationId"] == "op-456"
        assert outcome["retryAfter"] == "2"


@pytest.mark.parametrize("status", [503, 504])
def test_explicit_single_dispatch_never_replays_transient_mutation(status):
    evidence = _transport_fixture(status, single_dispatch=True, max_retries=3)
    assert evidence["calls"] == 1
    assert evidence["result"]["state"] == "outcome_unknown"


def test_explicit_zero_retries_is_honored_without_truthiness_fallback():
    evidence = _transport_fixture(503, single_dispatch=False, max_retries=0)
    assert evidence["calls"] == 1
    assert evidence["result"]["state"] == "outcome_unknown"


def test_connection_loss_after_dispatch_is_unknown_and_not_retried():
    evidence = _transport_fixture(None, network_error=True)
    assert evidence["calls"] == 1
    assert evidence["result"]["state"] == "outcome_unknown"
    assert evidence["result"]["statusCode"] is None
    assert evidence["result"]["dispatchCount"] == 1


@pytest.mark.parametrize("name", ["New-FabricWorkspace.ps1", "Update-FabricWorkspace.ps1"])
def test_reviewed_workspace_cmdlets_request_the_safe_transport_contract(name):
    text = Path("tools/MicrosoftFabricMgmt/source/Public/Workspace", name).read_text(encoding="utf-8-sig")
    assert "MaxRetries = 0" in text
    assert "SingleDispatch = $true" in text
    assert "ReturnTransportOutcome = $true" in text


def _raw_transport(state, status, *, dispatch_count=1):
    return json.dumps({
        "studio_envelope": 1,
        "success": True,
        "mode": "apply",
        "data": [{
            "studio_transport_outcome": 1,
            "state": state,
            "statusCode": status,
            "dispatchCount": dispatch_count,
            "correlationId": "corr-123",
            "id": "workspace-1" if status in {200, 201} else None,
            "operationId": "op-456" if status == 202 else None,
            "retryAfter": "2" if status == 202 else None,
        }],
        "error": None,
    })


@pytest.mark.parametrize("status,state", [(200, "succeeded"), (201, "succeeded"), (202, "accepted"), (204, "succeeded")])
def test_python_normalizer_preserves_success_and_async_transport_state(status, state):
    result = normalize(_raw_transport(state, status), "apply")
    assert result["data"][0]["state"] == state
    assert result["data"][0]["dispatchCount"] == 1


@pytest.mark.parametrize("status", [400, 403, 429])
def test_python_normalizer_maps_definite_http_rejection_to_failure(status):
    with pytest.raises(InvocationFailure):
        normalize(_raw_transport("failed", status), "apply")


@pytest.mark.parametrize("status", [503, 504, None])
def test_python_normalizer_maps_uncertain_dispatch_to_unknown(status):
    with pytest.raises(OutcomeUnknown):
        normalize(_raw_transport("outcome_unknown", status), "apply")


def test_python_normalizer_refuses_success_after_more_than_one_dispatch():
    with pytest.raises(OutcomeUnknown, match="dispatch count"):
        normalize(_raw_transport("succeeded", 201, dispatch_count=2), "apply")


def test_production_write_suspension_cannot_be_overridden_by_capability(monkeypatch):
    monkeypatch.setattr(admission, "WRITE_ADMISSION_SUSPENDED", True)
    for capability in combined_catalog():
        if capability.command in {"New-FabricWorkspace", "Update-FabricWorkspace"}:
            assert capability.execution_policy == "blocked"
            assert "tech-lead" in capability.blocked_reason
            capability.execution_policy = "guarded-write"
            with pytest.raises(UnsafeOperation):
                build_guarded_write_command(capability, {"WorkspaceName": "Lab"})
