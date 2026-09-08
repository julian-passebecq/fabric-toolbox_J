"""Offline browser fixture. Import this script only in tests; never in production."""
import os
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import activity, admission
from app.main import app
from app.providers.microsoftfabricmgmt import runtime


def connect(tenant):
    runtime._invalidate()
    if tenant=='fail':raise RuntimeError('Fixture authentication failure')
    runtime._connected=True
    runtime._tenant_id=tenant
    return {'success':True,'tenant_id':tenant,'generation':runtime._generation}


def run(command,*,mode='read'):
    data=[] if mode=='what-if' else [{'id':'workspace-one','displayName':'Fixture workspace','description':'=1+1,\n"quoted"'}]
    return {'studio_envelope':1,'success':True,'mode':mode,'data':data}


runtime.connect_interactive=connect
runtime.run_json=run
runtime._check_loaded_artifact=lambda:None
runtime.bind_artifact=lambda expected:'fixture-artifact'
runtime.artifact_fingerprint=lambda:'fixture-artifact'
# This script never dispatches an upstream operation. Enable candidate UI/broker
# states solely for the deterministic offline browser fixture.
admission.WRITE_ADMISSION_SUSPENDED=False
if __name__=='__main__':
    import uvicorn
    with tempfile.TemporaryDirectory(prefix='studio-fixture-') as directory:
        activity.ACTIVITY_FILE=Path(directory)/'activity.jsonl'
        uvicorn.run(app,host='127.0.0.1',port=int(os.environ['STUDIO_API_PORT']))
