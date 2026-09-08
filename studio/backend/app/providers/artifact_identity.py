"""Verify loaded function ASTs against repository bodies before guarded writes."""
import hashlib
import json
from pathlib import Path

from .outcomes import wrap_invocation
from ..admission import source_hash

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / 'tools/MicrosoftFabricMgmt/source'


def identity_probe():
    # Include all private helpers plus the explicitly admitted public call paths.
    reviewed = json.loads(Path(__file__).resolve().parents[1].joinpath('provider_sources.json').read_text())
    paths = [SOURCE / relative for relative in sorted(reviewed)]
    actual = {str(p.relative_to(SOURCE)).replace('\\','/'): source_hash(p) for p in paths}
    if actual != reviewed:
        raise RuntimeError('Provider helper source changed; execution review required')
    for relative in ['Workspace/Get-FabricWorkspace.ps1','Workspace/New-FabricWorkspace.ps1',
                     'Workspace/Update-FabricWorkspace.ps1','Capacity/Get-FabricCapacity.ps1',
                     'Workspace/Get-FabricWorkspaceRoleAssignment.ps1','Connections/Get-FabricConnection.ps1',
                     'Utils/Connect-FabricAccount.ps1']:
        path = SOURCE / 'Public' / relative
        if path not in paths:
            paths.append(path)
    entries = [(str(p), source_hash(p)) for p in paths]
    source_id = hashlib.sha256(json.dumps(entries).encode()).hexdigest()
    literals = ','.join("'"+p.replace("'","''")+"'" for p,_ in entries)
    command = """
$studioModule = Get-Module MicrosoftFabricMgmt;
if (@($studioModule).Count -ne 1) { throw 'Expected one loaded module' };
$studioMatch = & $studioModule {
    param($paths)
    foreach ($path in $paths) {
        $tokens = $null; $parseErrors = $null;
        $ast = [System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$parseErrors);
        if ($parseErrors.Count) { return $false };
        $function = $ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq [IO.Path]::GetFileNameWithoutExtension($path)},$true);
        if (-not $function) { return $false };
        $loaded = Get-Command $function.Name -CommandType Function -ErrorAction Stop;
        if ($loaded.ModuleName -ne 'MicrosoftFabricMgmt') { return $false };
        $loadedBody = $loaded.ScriptBlock.Ast;
        if ($loadedBody -is [System.Management.Automation.Language.FunctionDefinitionAst]) { $loadedBody = $loadedBody.Body };
        foreach ($part in @('ParamBlock','BeginBlock','ProcessBlock','EndBlock','DynamicParamBlock')) {
            $expected = ([string]$function.Body.$part).Replace("`r`n","`n").Trim();
            $actual = ([string]$loadedBody.$part).Replace("`r`n","`n").Trim();
            if ($expected -cne $actual) { return $false };
        }
    }
    return $true
} -paths @(""" + literals + """);
if ($studioMatch -ne $true) { throw 'Loaded provider differs from reviewed repository source' };
[PSCustomObject]@{ module_hash = (Get-FileHash -LiteralPath $studioModule.Path -Algorithm SHA256).Hash }
"""
    return source_id, wrap_invocation(command)
