import importlib.util
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from app import mutations
from app.catalog import combined_catalog
from app.models import SessionStatus
from app.mutations import MutationBroker
from app.providers.microsoftfabricmgmt import MicrosoftFabricMgmtRuntime, UnsafeOperation, UPSTREAM_SESSION_PATH
from app.providers.outcomes import InvocationFailure
from app.providers.session_extension import bounded_session_type


def envelope(mode, data=None):
    return dict(studio_envelope=1,success=True,mode=mode,data=[] if data is None else data)


@pytest.fixture
def setup(monkeypatch):
    runtime=MicrosoftFabricMgmtRuntime()
    runtime._connected=True
    runtime._tenant_id='tenant-a'
    monkeypatch.setattr(mutations,'runtime',runtime)
    monkeypatch.setattr(runtime,'_check_loaded_artifact',lambda:None)
    monkeypatch.setattr(runtime,'bind_artifact',lambda expected:'fixture-artifact')
    monkeypatch.setattr(runtime,'artifact_fingerprint',lambda:'fixture-artifact')
    catalog={c.id:c for c in combined_catalog()}
    broker=MutationBroker()
    monkeypatch.setattr(broker,'_capability',lambda id:catalog[id].model_copy(deep=True))
    calls=[]
    def run(command, *, mode='read'):
        calls.append(mode)
        if mode=='apply':
            return envelope(mode,[{'id':'one'}])
        if mode=='read':
            return envelope(mode,[{'id':'one','displayName':'Lab','description':'new'}])
        return envelope(mode)
    monkeypatch.setattr(runtime,'run_json',run)
    return broker,runtime,catalog,calls


def create(setup,update=False):
    b,r,c,calls=setup
    return b.create_plan(c['ps-workspace-update-fabricworkspace' if update else 'ps-workspace-new-fabricworkspace'],{'WorkspaceId':'one','WorkspaceDescription':'new'} if update else {'WorkspaceName':'Lab'})


def test_detached_and_tamper(setup):
    b,*_=setup
    p=create(setup)
    p.parameters['WorkspaceName']='tampered'
    b.get(p.plan_id).parameters['WorkspaceName']='tampered'
    b.list()[0].parameters.clear()
    assert b.get(p.plan_id).parameters=={'WorkspaceName':'Lab'}
    b._plans[p.plan_id].validation_command='tampered'
    with pytest.raises(UnsafeOperation,match='snapshot'):
        b.validate(p.plan_id)


def test_generation_invalidates_same_tenant(setup):
    b,r,*_=setup
    p=create(setup)
    r._invalidate()
    r._connected=True
    r._tenant_id='tenant-a'
    with pytest.raises(UnsafeOperation,match='generation'):
        b.validate(p.plan_id)


def test_duplicate_apply_and_responsive_list(setup,monkeypatch):
    b,r,c,calls=setup
    p=create(setup)
    b.validate(p.plan_id)
    entered,release=threading.Event(),threading.Event()
    original=r.run_json
    def run(command,*,mode='read'):
        if mode=='apply':
            entered.set()
            assert release.wait(5)
        return original(command,mode=mode)
    monkeypatch.setattr(r,'run_json',run)
    with ThreadPoolExecutor(2) as pool:
        one=pool.submit(b.execute,p.plan_id,p.confirmation_text)
        assert entered.wait(5)
        assert b.get(p.plan_id).status=='executing'
        assert b.list()[0].status=='executing'
        with pytest.raises(UnsafeOperation):
            b.execute(p.plan_id,p.confirmation_text)
        release.set()
        assert one.result(5).plan.status=='executed'
    assert calls.count('apply')==1
    with pytest.raises(UnsafeOperation):
        b.execute(p.plan_id,p.confirmation_text)


def test_validation_races(setup,monkeypatch):
    b,r,c,calls=setup
    p=create(setup)
    entered,release=threading.Event(),threading.Event()
    def run(command,*,mode='read'):
        entered.set()
        assert release.wait(5)
        return envelope(mode)
    monkeypatch.setattr(r,'run_json',run)
    with ThreadPoolExecutor(1) as pool:
        first=pool.submit(b.validate,p.plan_id)
        assert entered.wait(5)
        with pytest.raises(UnsafeOperation): b.validate(p.plan_id)
        with pytest.raises(UnsafeOperation): b.execute(p.plan_id,p.confirmation_text)
        release.set()
        assert first.result(5).plan.status=='validated'
    with pytest.raises(UnsafeOperation): b.validate(p.plan_id)


@pytest.mark.parametrize('failure,status',[(InvocationFailure('fail'),'failed'),(TimeoutError('uncertain'),'outcome_unknown')])
def test_apply_failures_no_replay(setup,monkeypatch,failure,status):
    b,r,c,calls=setup
    p=create(setup);b.validate(p.plan_id)
    def run(*args,**kwargs): raise failure
    monkeypatch.setattr(r,'run_json',run)
    assert b.execute(p.plan_id,p.confirmation_text).plan.status==status
    with pytest.raises(UnsafeOperation): b.execute(p.plan_id,p.confirmation_text)


@pytest.mark.parametrize('apply,read,update,status',[
    ([],[],False,'applied_unverified'),
    ([{'id':'one'}],[{'id':'wrong','displayName':'Lab'}],False,'applied_unverified'),
    ([{'id':'one'}],[{'id':'one','displayName':'Lab'},{'id':'one','displayName':'Lab'}],False,'applied_unverified'),
    ([{'id':'one'}],[{'id':'one','displayName':'old'}],False,'applied_unverified'),
    ([],[{'id':'one','description':'new','displayName':'unrelated'}],True,'executed'),
    ([],[{'id':'one','description':'old'}],True,'applied_unverified'),
])
def test_verification_matrix(setup,monkeypatch,apply,read,update,status):
    b,r,c,calls=setup
    p=create(setup,update);b.validate(p.plan_id)
    monkeypatch.setattr(r,'run_json',lambda command,mode='read':envelope(mode,apply if mode=='apply' else read))
    assert b.execute(p.plan_id,p.confirmation_text).plan.status==status


def test_expiry_during_apply_does_not_relabel(setup,monkeypatch):
    b,r,c,calls=setup
    p=create(setup);b.validate(p.plan_id)
    now=mutations._utcnow()
    original=r.run_json
    def run(command,mode='read'):
        monkeypatch.setattr(mutations,'_utcnow',lambda:now+timedelta(hours=1))
        assert b.get(p.plan_id).status=='executing'
        return original(command,mode=mode)
    monkeypatch.setattr(r,'run_json',run)
    assert b.execute(p.plan_id,p.confirmation_text).plan.status=='executed'


def test_queued_read_checks_generation_at_dispatch(setup):
    b,r,c,calls=setup
    expected=r.status()
    with ThreadPoolExecutor(1) as pool:
        with r._lock:
            future=pool.submit(r.execute_read,c['ps-workspace-get-fabricworkspace'],{},expected=expected)
            r._invalidate();r._connected=True;r._tenant_id='tenant-b'
        with pytest.raises(UnsafeOperation): future.result(5)
    assert not calls


def test_upstream_no_output_watchdog_joins_owned_process():
    spec=importlib.util.spec_from_file_location('test_upstream',UPSTREAM_SESSION_PATH)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    cls=bounded_session_type(module.PowerShellSession)
    session=object.__new__(cls)
    process=subprocess.Popen([sys.executable,'-u','-c','import time; time.sleep(60)'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    session._process=process;session._timeout=0.2;session._stderr_thread=None
    started=time.monotonic()
    with pytest.raises(Exception): session._read_until_sentinel()
    assert time.monotonic()-started<12
    assert process.poll() is not None
    assert session._process is None
    with pytest.raises(RuntimeError): session.run('ignored')


def test_real_persistent_powershell_success_stall_and_cleanup(tmp_path):
    from app.providers.outcomes import normalize, wrap_invocation
    runtime=MicrosoftFabricMgmtRuntime()
    cls=runtime._load_session_type()
    module=tmp_path/'Harmless.psm1'
    module.write_text('function Get-Fixture { @{id="one"} }')
    session=cls(module_path=module,timeout=3)
    process=session._process
    worker=session._stderr_thread
    try:
        assert normalize(session.run(wrap_invocation('Get-Fixture')))['data']==[{'id':'one'}]
        started=time.monotonic()
        with pytest.raises(Exception):session.run('Start-Sleep -Seconds 60')
        assert time.monotonic()-started<12
        assert process.poll() is not None and not worker.is_alive()
        with pytest.raises(RuntimeError):session.run('Get-Fixture')
    finally:session.close()


@pytest.mark.parametrize('field,value',[('expires_at','2099-01-01T00:00:00Z'),('session_generation','tamper'),('rendered_command','tamper'),('parameters',{'WorkspaceName':'tamper'}),('digest','0'*64)])
def test_each_approval_field_is_checked(setup,field,value):
    b,r,c,calls=setup
    p=create(setup)
    setattr(b._plans[p.plan_id],field,value)
    with pytest.raises(UnsafeOperation): b.validate(p.plan_id)
    assert not calls


def test_queue_expiry_blocks_actual_dispatch(setup,monkeypatch):
    b,r,c,calls=setup
    p=create(setup);b.validate(p.plan_id)
    now=mutations._utcnow()
    queued=threading.Event()
    original=r.execute_guarded_write
    def execute(*args,**kwargs):
        queued.set()
        return original(*args,**kwargs)
    monkeypatch.setattr(r,'execute_guarded_write',execute)
    with ThreadPoolExecutor(1) as pool:
        with r._lock:
            future=pool.submit(b.execute,p.plan_id,p.confirmation_text)
            assert queued.wait(5)
            monkeypatch.setattr(mutations,'_utcnow',lambda:now+timedelta(hours=1))
        assert future.result(5).plan.status=='failed'
    assert calls.count('apply')==0


@pytest.mark.parametrize('fail_start',[True,False])
def test_audit_disk_failure_no_replay(setup,monkeypatch,fail_start):
    b,r,c,calls=setup
    p=create(setup);b.validate(p.plan_id)
    original=mutations.append_activity
    def append(event):
        if (event['status']=='started')==fail_start:raise OSError('fixture disk failure')
        return original(event)
    monkeypatch.setattr(mutations,'append_activity',append)
    result=b.execute(p.plan_id,p.confirmation_text)
    if fail_start:
        assert result.plan.status=='failed' and calls.count('apply')==0
    else:
        assert result.plan.status=='executed' and result.plan.audit_warning
    with pytest.raises(UnsafeOperation):b.execute(p.plan_id,p.confirmation_text)
