import subprocess
from pathlib import Path
from app.catalog import combined_catalog
from app.providers.fabric_rest import build_rest_get_command
from app.providers.outcomes import normalize


def test_registered_rest_uses_actual_module_auth_context_and_array_output(tmp_path):
    helper=Path('tools/MicrosoftFabricMgmt/source/Public/Utils/Invoke-FabricAPIRequest.ps1').resolve()
    module=tmp_path/'MicrosoftFabricMgmt.psm1'
    body="""
$script:FabricAuthContext=@{FabricHeaders=@{fixture='value'}}
function Invoke-FabricAuthCheck {}
function Write-FabricLog {}
function Get-PSFConfigValue { param($FullName,$Fallback); return $Fallback }
function Invoke-RestMethod {
 param($Headers,$Uri,$Method,$ErrorAction,[switch]$SkipHttpErrorCheck,$StatusCodeVariable,$ResponseHeadersVariable)
 if ($Method -ne 'Get' -or $Headers.fixture -ne 'value') { throw 'Bad read fixture contract' }
 Set-Variable -Scope 1 -Name $StatusCodeVariable -Value 200
 Set-Variable -Scope 1 -Name $ResponseHeadersVariable -Value @{}
 return [PSCustomObject]@{value=@([PSCustomObject]@{id='one';error='domain'})}
}
"""+"\n. '"+str(helper).replace("'","''")+"'"
    module.write_text(body)
    capability=next(c for c in combined_catalog() if c.id=='rest-items-list')
    command=build_rest_get_command(capability,{'workspaceId':'workspace'})
    result=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',"Import-Module '"+str(module)+"' -WarningAction SilentlyContinue; "+command],capture_output=True,text=True,timeout=20,check=True)
    assert normalize(result.stdout)['data']==[{'id':'one','error':'domain'}]
