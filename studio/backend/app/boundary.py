import hmac
import os
import time
import uuid

from starlette.responses import JSONResponse
from .activity import append_activity


async def local_boundary(request, call_next):
    token=os.environ.get('STUDIO_CLIENT_TOKEN','')
    api_port=os.environ.get('STUDIO_API_PORT','8765')
    ui_port=os.environ.get('STUDIO_UI_PORT','5173')
    hosts={f'127.0.0.1:{api_port}',f'localhost:{api_port}'}
    origins={f'http://127.0.0.1:{ui_port}',f'http://localhost:{ui_port}'}
    rejection=None
    if request.headers.get('host') not in hosts or (request.headers.get('origin') is not None and request.headers['origin'] not in origins):
        rejection=JSONResponse({'detail':'Untrusted local client host/origin'},status_code=403)
    elif request.url.path!='/api/health':
        if not token:
            rejection=JSONResponse({'detail':'Start Studio with the supported launcher; STUDIO_CLIENT_TOKEN is missing'},status_code=503)
        elif not hmac.compare_digest(request.headers.get('x-studio-client','').encode(),token.encode()):
            rejection=JSONResponse({'detail':'Client credential required'},status_code=401)
    run_id=str(uuid.uuid4())
    started=time.monotonic()
    path=request.url.path
    action='session.connect' if path=='/api/session/connect' else 'capability.execute' if '/capabilities/' in path and path.endswith('/execute') else 'request'
    event={'action':action,'run_id':run_id,'status':'started'}
    try:
        if request.method!='GET' or rejection: append_activity(event)
    except OSError:
        return JSONResponse({'detail':'Cannot persist required audit start'},status_code=503)
    try:
        response=rejection or await call_next(request)
    except Exception:
        response=JSONResponse({'detail':'Local operation failed; inspect activity and current state before retrying a write'},status_code=500)
    if request.method!='GET' or rejection:
        try:
            status='rejected' if rejection or 400<=response.status_code<500 else 'failed' if response.status_code>=500 else 'succeeded'
            append_activity({**event,'status':status,'http_status':response.status_code,'duration_ms':round((time.monotonic()-started)*1000,2)})
        except OSError:
            response.headers['X-Studio-Audit-Warning']='Outcome could not be persisted; do not replay a write'
    response.headers['X-Studio-Run-Id']=run_id
    return response
