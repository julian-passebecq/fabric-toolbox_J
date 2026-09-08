import json

import pytest
from fastapi.testclient import TestClient
from app import main, mutations
from app.catalog import combined_catalog
from app.mutations import MutationBroker
from app.providers.microsoftfabricmgmt import MicrosoftFabricMgmtRuntime


@pytest.fixture
def api(monkeypatch):
    catalog=combined_catalog()
    monkeypatch.setattr(main,'combined_catalog',lambda:catalog)
    monkeypatch.setattr(mutations,'combined_catalog',lambda:catalog)
    runtime=MicrosoftFabricMgmtRuntime()
    calls=[]
    control={'failure':False}
    class Session:
        alive=True
        def _is_alive(self): return self.alive
        def close(self): self.alive=False
        def run(self,command):
            mode=next(m for m in ['connect','what-if','apply','read'] if f"mode = '{m}'" in command)
            calls.append(mode)
            if control['failure']:return json.dumps({'success':False,'error':'fixture','error_type':'FixtureError'})
            data=[] if mode in {'connect','what-if'} else [{'id':'one','displayName':'Lab','error':'domain-data'}]
            return json.dumps(dict(studio_envelope=1,success=True,mode=mode,data=data))
    monkeypatch.setattr(runtime,'_load_session_type',lambda:Session)
    monkeypatch.setattr(runtime,'_check_loaded_artifact',lambda:None)
    monkeypatch.setattr(runtime,'bind_artifact',lambda expected:'fixture-artifact')
    monkeypatch.setattr(runtime,'artifact_fingerprint',lambda:'fixture-artifact')
    monkeypatch.setattr(main,'runtime',runtime);monkeypatch.setattr(mutations,'runtime',runtime)
    broker=MutationBroker();monkeypatch.setattr(main,'broker',broker)
    monkeypatch.setenv('STUDIO_CLIENT_TOKEN','fixture-client')
    with TestClient(main.app,base_url='http://127.0.0.1:8765',headers={'X-Studio-Client':'fixture-client'}) as client:
        yield client,runtime,calls,control,broker
    runtime.close()


def connect(api):
    client,runtime,*_=api
    response=client.post('/api/session/connect',json={'tenant_id':'tenant-a'})
    assert response.status_code==200
    client.headers['X-Studio-Session']=response.json()['generation']


def test_complete_route_validation_apply_and_terminal_retry(api):
    client,runtime,calls,control,broker=api
    connect(api)
    read=client.post('/api/capabilities/ps-workspace-get-fabricworkspace/execute',json={'parameters':{}})
    assert read.status_code==200 and read.json()['result']['data'][0]['error']=='domain-data'
    plan=client.post('/api/capabilities/ps-workspace-new-fabricworkspace/mutations/plan',json={'parameters':{'WorkspaceName':'Lab'}}).json()
    path=f"/api/mutations/{plan['plan_id']}"
    assert client.post(path+'/execute',json={'confirmation':plan['confirmation_text']}).status_code==400
    assert client.post(path+'/validate').json()['plan']['status']=='validated'
    assert client.post(path+'/execute',json={'confirmation':'wrong'}).status_code==400
    applied=client.post(path+'/execute',json={'confirmation':plan['confirmation_text']})
    assert applied.json()['plan']['status']=='executed'
    assert client.post(path+'/execute',json={'confirmation':plan['confirmation_text']}).status_code==400
    assert calls.count('apply')==1


def test_upstream_failure_connect_read_validate(api):
    client,runtime,calls,control,broker=api
    connect(api)
    old=runtime.status().generation
    plan=client.post('/api/capabilities/ps-workspace-new-fabricworkspace/mutations/plan',json={'parameters':{'WorkspaceName':'Lab'}}).json()
    control['failure']=True
    assert client.post('/api/capabilities/ps-workspace-get-fabricworkspace/execute',json={'parameters':{}}).status_code==502
    assert client.post(f"/api/mutations/{plan['plan_id']}/validate").json()['plan']['status']=='validation_failed'
    assert client.post('/api/session/connect',json={'tenant_id':'tenant-a'}).status_code==503
    assert not runtime.status().connected and runtime.status().generation!=old


def test_unknown_command_capacity_and_stale_client_generation_do_not_dispatch(api):
    client,runtime,calls,control,broker=api
    connect(api)
    for params in [{'WorkspaceName':'Lab','CapacityId':'capacity'},{'WorkspaceName':False}]:
        preview=client.post('/api/capabilities/ps-workspace-new-fabricworkspace/preview',json={'parameters':params})
        assert not preview.json()['executable']
        assert client.post('/api/capabilities/ps-workspace-new-fabricworkspace/mutations/plan',json={'parameters':params}).status_code==400
    assert client.post('/api/capabilities/unknown/execute').status_code==404
    assert client.post('/api/capabilities/ps-environment-publish-fabricenvironment/execute').status_code==400
    client.headers['X-Studio-Session']='old'
    assert client.post('/api/capabilities/ps-workspace-get-fabricworkspace/execute').status_code==409
    assert calls==['connect']
