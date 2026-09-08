"""Executed reproductions of the upstream defects requiring lead review."""
import json
import subprocess

import pytest

from app import admission
from app.catalog import combined_catalog
from app.providers.microsoftfabricmgmt import build_guarded_write_command, UnsafeOperation


@pytest.mark.parametrize('status,expected_calls',[(503,4),(504,4),(204,1)])
def test_upstream_zero_retries_and_204_defect(status,expected_calls):
    script="""
$script:calls=0
function Write-FabricLog {}
function Get-PSFConfigValue { param($FullName,$Fallback); return $Fallback }
function Get-FabricRetryDelay { return 0 }
function Start-Sleep {}
function Invoke-RestMethod {
    param($Headers,$Uri,$Method,$Body,$ContentType,$ErrorAction,[switch]$SkipHttpErrorCheck,$StatusCodeVariable,$ResponseHeadersVariable)
    $script:calls++
    Set-Variable -Scope 1 -Name $StatusCodeVariable -Value STATUS
    Set-Variable -Scope 1 -Name $ResponseHeadersVariable -Value @{}
    return [PSCustomObject]@{message='fixture HTTP response'}
}
. './tools/MicrosoftFabricMgmt/source/Public/Utils/Invoke-FabricAPIRequest.ps1'
$failed=$false
try { Invoke-FabricAPIRequest -Headers @{fixture='value'} -BaseURI 'https://unused.invalid' -Method Post -MaxRetries 0 | Out-Null }
catch { $failed=$true }
@{calls=$script:calls;failed=$failed} | ConvertTo-Json -Compress
""".replace('STATUS',str(status))
    result=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=20,check=True)
    evidence=json.loads(result.stdout)
    assert evidence=={'calls':expected_calls,'failed':True}


def test_production_write_suspension_cannot_be_overridden_by_capability(monkeypatch):
    monkeypatch.setattr(admission,'WRITE_ADMISSION_SUSPENDED',True)
    for c in combined_catalog():
        if c.command in {'New-FabricWorkspace','Update-FabricWorkspace'}:
            assert c.execution_policy=='blocked'
            assert 'tech-lead' in c.blocked_reason
            c.execution_policy='guarded-write'
            with pytest.raises(UnsafeOperation):build_guarded_write_command(c,{'WorkspaceName':'Lab'})
