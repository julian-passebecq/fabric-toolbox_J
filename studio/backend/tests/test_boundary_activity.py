import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app import activity, mutations
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('STUDIO_CLIENT_TOKEN','synthetic-credential')
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        yield client


@pytest.mark.parametrize('path',['/api/session','/api/capabilities','/api/activity','/api/mutations','/api/diagnostics','/docs','/openapi.json'])
def test_protected_routes(client,path):
    assert client.get(path).status_code==401
    assert client.get(path,headers={'X-Studio-Client':'bad'}).status_code==401


def test_minimal_health_and_host_origin(client):
    assert client.get('/api/health').status_code==200
    headers={'X-Studio-Client':'synthetic-credential'}
    assert client.get('/api/session',headers=headers).status_code==200
    assert client.get('/api/session',headers={**headers,'Origin':'https://foreign.example'}).status_code==403
    assert client.get('/api/session',headers={**headers,'Host':'foreign.example'}).status_code==403
    assert client.get('/api/session',headers={**headers,'Origin':'http://127.0.0.1:5173'}).status_code==200


def test_missing_configuration_fails_closed(client,monkeypatch):
    monkeypatch.delenv('STUDIO_CLIENT_TOKEN')
    assert client.get('/api/session').status_code==503


def test_invalid_request_audited_without_secrets(client):
    response=client.post('/api/session/connect',json={'tenant_id':'secret-value'},headers={'X-Studio-Client':'secret-value'})
    assert response.status_code==401
    rows=activity.read_activity()
    assert any(r['status']=='rejected' and r['duration_ms']>=0 and r['run_id'] for r in rows)
    assert b'secret-value' not in activity.ACTIVITY_FILE.read_bytes()


def test_nested_secrets_and_legacy_exports_are_redacted():
    secret='SYNTHETIC-SECRET-NEVER-DURABLE'
    activity.append_activity({'action':'capability.execute','parameters':{'WorkspaceName':secret},'rendered_command':secret,'result':{'data':[{'error':secret}]},'error':secret})
    assert secret not in activity.ACTIVITY_FILE.read_text()
    with activity.ACTIVITY_FILE.open('a') as handle:
        handle.write(json.dumps({'timestamp':'2026-09-08T00:00:00+00:00','action':'old','result':secret})+'\n')
    assert secret not in json.dumps(activity.read_activity())


def test_rotation_and_corrupt_tail(monkeypatch):
    monkeypatch.setattr(activity,'MAX_FILE_BYTES',800)
    for _ in range(40): activity.append_activity({'action':'request','run_id':str(uuid.uuid4())})
    assert len(list(activity.ACTIVITY_FILE.parent.glob('activity.jsonl*')))<=activity.ROTATIONS+1
    with activity.ACTIVITY_FILE.open('ab') as handle:handle.write(b'{broken\n'+b'x'*5000+b'\n')
    assert activity.read_activity(100000)
    assert len(activity.read_activity(2))<=2
    assert all(len(json.dumps(r).encode())<activity.MAX_RECORD_BYTES for r in activity.read_activity())


def test_orphan_start_after_restart(monkeypatch):
    activity.append_activity({'status':'started','attempt_id':str(uuid.uuid4())})
    monkeypatch.setattr(activity,'BOOT_ID',str(uuid.uuid4()))
    assert activity.read_activity()[0]['status']=='interrupted_unknown'


def test_start_disk_failure_rejects_request(client,monkeypatch):
    from app import boundary
    def fail(event):raise OSError('disk fixture')
    monkeypatch.setattr(boundary,'append_activity',fail)
    response=client.post('/api/session/connect',json={'tenant_id':'x'},headers={'X-Studio-Client':'synthetic-credential'})
    assert response.status_code==503
