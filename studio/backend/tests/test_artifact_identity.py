import subprocess
from pathlib import Path

import pytest

from app.providers.artifact_identity import SOURCE, identity_probe
from app.providers.outcomes import normalize, InvocationFailure


@pytest.mark.parametrize('drift',[False,True])
def test_loaded_function_identity_with_harmless_module(tmp_path,drift):
    # Dot-source definitions only; no upstream function is invoked.
    module=tmp_path/'MicrosoftFabricMgmt.psm1'
    paths=list((SOURCE/'Private').rglob('*.ps1'))+list((SOURCE/'Public').rglob('*.ps1'))
    body='\n'.join(". '"+str(p).replace("'","''")+"'" for p in paths)
    if drift:body+="\nfunction New-FabricWorkspace { param($WorkspaceName) throw 'drift fixture' }"
    module.write_text(body,encoding='utf-8')
    _,command=identity_probe()
    result=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',"Import-Module '"+str(module).replace("'","''")+"' -WarningAction SilentlyContinue; "+command],capture_output=True,text=True,encoding='utf-8',timeout=30,check=True)
    if drift:
        with pytest.raises(InvocationFailure):normalize(result.stdout)
    else:
        assert len(normalize(result.stdout)['data'][0]['module_hash'])==64
