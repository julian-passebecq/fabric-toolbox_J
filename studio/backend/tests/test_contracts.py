import json
import subprocess

import pytest

from app.catalog import combined_catalog
from app.contracts import validate_parameters, parse_endpoint
from app.models import Capability, ParameterSpec
from app.providers.microsoftfabricmgmt import build_read_command, build_guarded_write_command, _ps_literal, UnsafeOperation
from app.providers.fabric_rest import build_rest_get_command
from app.providers.outcomes import normalize, InvocationFailure, OutcomeUnknown, wrap_invocation


@pytest.fixture(scope='module')
def catalog():
    from app import admission
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(admission,'WRITE_ADMISSION_SUSPENDED',False)
        return {c.id: c for c in combined_catalog()}


@pytest.mark.parametrize('verb', ['Publish','Approve','Revoke','Move','Restore','Enable','Disable','Import','Get','Connect'])
def test_unknown_commands_never_authorize(verb):
    c = Capability(id='new',title='new',category='test',provider='MicrosoftFabricMgmt',source='test',command=f'{verb}-NewThing',execution_policy='read')
    with pytest.raises(UnsafeOperation):
        build_read_command(c)


def test_baseline_unsafe_commands_and_drift(catalog):
    for c in catalog.values():
        if c.command and c.command.split('-')[0] in {'Publish','Approve','Revoke','Move','Restore','Enable','Disable','Import'}:
            with pytest.raises(UnsafeOperation):
                build_read_command(c)
    c = catalog['ps-workspace-get-fabricworkspace'].model_copy(deep=True)
    c.source_path = 'missing.ps1'
    with pytest.raises(UnsafeOperation):
        build_read_command(c)
    c = catalog['rest-items-list'].model_copy(deep=True)
    c.endpoint = 'GET /v1/other'
    with pytest.raises(UnsafeOperation):
        build_rest_get_command(c)


@pytest.mark.parametrize('params', [{}, {'WorkspaceName':''}, {'WorkspaceName':'  '}, {'WorkspaceName':False}, {'WorkspaceName':'Lab','CapacityId':'capacity'}, {'WorkspaceName':'Lab','extra':'x'}])
def test_create_rejects_invalid_input(catalog, params):
    with pytest.raises(ValueError):
        build_guarded_write_command(catalog['ps-workspace-new-fabricworkspace'],params)


def test_exclusivity_and_switch_false(catalog):
    c = catalog['ps-workspace-get-fabricworkspace']
    with pytest.raises(ValueError,match='exclusive'):
        build_read_command(c, {'WorkspaceId':'id','WorkspaceName':'name'})
    assert '-Raw:$false' in build_read_command(c,{'Raw':False})
    assert '-Raw' not in build_read_command(c,{})


@pytest.mark.parametrize('kind,value,valid', [('bool',False,True),('bool',0,False),('int',True,False),('int',2**32,False),('int64',2**40,True),('guid','bad',False),('guid','00000000-0000-0000-0000-000000000001',True),('string[]',['a','b'],True),('string[]',['a',1],False),('object',{},False),('datetime','today',False),('string',None,False)])
def test_types(kind,value,valid):
    c=Capability(id='type',title='type',category='test',provider='test',source='test',parameters=['p'],parameter_specs=[ParameterSpec(name='p',type=kind)])
    if valid:
        assert validate_parameters(c,{'p':value}) == {'p':value}
    else:
        with pytest.raises(ValueError):
            validate_parameters(c,{'p':value})


def test_validate_set_and_explicit_false_boolean_rendering():
    from app.providers.microsoftfabricmgmt import _command_invocation
    c=Capability(id='fixture',title='fixture',category='test',provider='MicrosoftFabricMgmt',source='test',command='Get-Fixture',parameters=['Mode','Flag'],parameter_specs=[ParameterSpec(name='Mode',allowed_values=['One','Two']),ParameterSpec(name='Flag',type='bool')])
    with pytest.raises(ValueError,match='ValidateSet'):validate_parameters(c,{'Mode':'Three'})
    assert validate_parameters(c,{'Mode':'one'})=={'Mode':'one'}
    assert '-Flag $false' in _command_invocation(c,{'Flag':False})


@pytest.mark.parametrize('value',[float('nan'),float('inf'),object(),{}])
def test_renderer_rejects_unsupported_values(value):
    with pytest.raises(ValueError):
        _ps_literal(value)


def test_literal_round_trip_in_powershell():
    value = ["O'Brien", 'line\nnext', '日本語', "$(throw 'injected'); `x"]
    result = subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',"[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "+_ps_literal(value)+' | ConvertTo-Json -Compress'],capture_output=True,text=True,encoding='utf-8',timeout=20,check=True)
    assert json.loads(result.stdout) == value


@pytest.mark.parametrize('data',[[],[{'id':'one'}],[{'error':'domain data'}],[[{'id':'nested'}]]])
def test_payload_preserved(data):
    expected = data[0] if len(data)==1 and isinstance(data[0],list) else data
    assert normalize(json.dumps(dict(studio_envelope=1,success=True,mode='read',data=data)))['data']==expected


@pytest.mark.parametrize('raw', ['','null','[]','{}','plain','{"success":true,"output":null}','{"studio_envelope":1,"success":true,"mode":"read","data":["text"]}'])
def test_no_blanket_success(raw):
    with pytest.raises(OutcomeUnknown):
        normalize(raw)


def test_upstream_error_not_payload():
    with pytest.raises(InvocationFailure):
        normalize('{"success":false,"error":"x","error_type":"Exception"}')


@pytest.mark.parametrize('failure', [False,True])
@pytest.mark.parametrize('what_if',[False,True])
def test_actual_workspace_catch_and_whatif(catalog, failure, what_if):
    # Run original workspace and logger bodies; harmless dependencies have no network.
    auth = "throw 'fixture authentication failure'" if failure else ''
    script = f"function Invoke-FabricAuthCheck {{ {auth} }}\n" + """
function New-FabricAPIUri { 'unused' }
function Convert-FabricRequestBody { '{}' }
function Invoke-FabricAPIRequest { @{id='one';displayName='Lab'} }
function Write-PSFMessage { param($Message,$Level,$FunctionName,$ModuleName,$ErrorRecord) }
. './tools/MicrosoftFabricMgmt/source/Private/Write-FabricLog.ps1'
. './tools/MicrosoftFabricMgmt/source/Public/Workspace/New-FabricWorkspace.ps1'
""" + build_guarded_write_command(catalog['ps-workspace-new-fabricworkspace'],{'WorkspaceName':'Lab'},what_if=what_if)
    result = subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,encoding='utf-8',timeout=20,check=True)
    mode = 'what-if' if what_if else 'apply'
    if failure:
        with pytest.raises(InvocationFailure):
            normalize(result.stdout,mode)
    else:
        assert normalize(result.stdout,mode)['success'] is True


@pytest.mark.parametrize('command',["throw 'terminated'", "Write-Error 'non terminating' -ErrorAction Continue", "try { throw 'caught' } catch {}"])
def test_stream_errors(command):
    result=subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',wrap_invocation(command,'what-if')],capture_output=True,text=True,timeout=20,check=True)
    with pytest.raises(InvocationFailure):
        normalize(result.stdout,'what-if')


def test_rest_baseline_and_bad_declarations(catalog):
    for c in catalog.values():
        if c.provider=='Fabric REST API' and c.execution_policy=='read':
            assert parse_endpoint(c)[0]=='GET'
    for endpoint in ['GET /v1/{bad','GET /v1/{missing}','GET /v1/../bad','BOGUS /v1/x','/v1/x']:
        c=catalog['rest-items-list'].model_copy(update={'endpoint':endpoint})
        with pytest.raises(ValueError):
            parse_endpoint(c)


def test_duplicate_raw_registry_rejected(monkeypatch):
    from app import catalog as module
    monkeypatch.setattr(module,'discover_powershell_capabilities',lambda:[])
    monkeypatch.setattr(module,'load_static_entries',lambda:[{'id':'a'},{'id':'a'}])
    with pytest.raises(ValueError,match='Duplicate raw'):
        module.combined_catalog()
