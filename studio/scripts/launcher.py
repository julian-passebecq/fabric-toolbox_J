"""Supported repository launcher; no tenant operations during startup checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
HIDDEN=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0


def checked(argv, **kwargs):
    return subprocess.run([str(x) for x in argv],check=True,text=True,creationflags=HIDDEN,**kwargs)


def assert_free(port):
    with socket.socket() as listener:
        try: listener.bind(('127.0.0.1',port))
        except OSError as exc: raise RuntimeError(f'Port {port} is already occupied; stop its owner or choose another port') from exc


def stop_owned(process):
    if process.poll() is not None: return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=HIDDEN,timeout=10)
    else: process.terminate()
    try: process.wait(timeout=10)
    except subprocess.TimeoutExpired: process.kill();process.wait(timeout=10)


def wait_ready(url, processes, timeout=45):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if any(p.poll() is not None for p in processes): raise RuntimeError('A Studio child exited during startup; inspect studio/.run logs')
        try:
            with urllib.request.urlopen(url,timeout=1) as response:
                if response.status==200: return
        except (OSError,TimeoutError): pass
        time.sleep(0.1)
    raise RuntimeError('Studio readiness deadline exceeded; inspect studio/.run logs')


def install_fingerprint():
    digest=hashlib.sha256()
    for name in ['package-lock.json','package.json','frontend/package.json','backend/requirements.lock','backend/pyproject.toml']:
        digest.update((ROOT/name).read_bytes())
    return digest.hexdigest()


def main():
    parser=argparse.ArgumentParser()
    for flag in ['skip-install','no-browser','check-only','smoke-test']:parser.add_argument('--'+flag,action='store_true')
    parser.add_argument('--api-port',type=int,default=8765)
    parser.add_argument('--ui-port',type=int,default=5173)
    args=parser.parse_args()
    if sys.version_info[:2]!=(3,13):raise RuntimeError('Studio requires Python 3.13')
    node=shutil.which('node');npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm');pwsh=shutil.which('pwsh')
    if not all([node,npm,pwsh]):raise RuntimeError('Install Node 22, npm, and PowerShell 7 and put them on PATH')
    version=checked([node,'--version'],capture_output=True).stdout.strip().lstrip('v').split('.')
    if int(version[0])!=22 or int(version[1])<12:raise RuntimeError('Studio requires Node 22.12 or newer in major 22')
    ps_version=checked([pwsh,'-NoProfile','-NonInteractive','-Command','$PSVersionTable.PSVersion.Major'],capture_output=True).stdout.strip()
    if ps_version!='7':raise RuntimeError('Studio requires PowerShell 7')
    for port in [args.api_port,args.ui_port]:
        if not 1024<=port<=65535:raise RuntimeError('Ports must be between 1024 and 65535')
        assert_free(port)
    if args.api_port==args.ui_port:raise RuntimeError('API and UI ports must differ')
    venv=ROOT/'backend/.venv'
    python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists():
        if args.skip_install:raise RuntimeError('SkipInstall requires the installed backend environment')
        checked([sys.executable,'-m','venv',venv])
    state=ROOT/'.install-state.json'
    fingerprint=install_fingerprint()
    if not args.skip_install:
        checked([python,'-m','pip','install','-r',ROOT/'backend/requirements.lock'])
        checked([python,'-m','pip','install','--no-deps','--no-build-isolation','-e',ROOT/'backend'])
        checked([npm,'ci'],cwd=ROOT)
    elif not state.exists() or json.loads(state.read_text()).get('fingerprint')!=fingerprint:
        raise RuntimeError('SkipInstall dependencies are stale or unverified; run once without SkipInstall')
    checked([python,'-c',"import app.main, app.providers.fabric_rest, app.providers.session_extension; import sys; assert sys.version_info[:2] == (3,13)"],cwd=ROOT/'backend')
    checked([python,'-m','pip','check'])
    checked([npm,'ls','--all','--json'],cwd=ROOT,capture_output=True)
    # Check locked Python versions, including tests and build tooling.
    requirements=[line.strip() for line in (ROOT/'backend/requirements.lock').read_text().splitlines() if '==' in line]
    code="import importlib.metadata as m,json,sys; assert all(m.version(n)==v for n,v in (x.split('==') for x in json.loads(sys.argv[1])))"
    checked([python,'-c',code,json.dumps(requirements)])
    state.write_text(json.dumps({'fingerprint':fingerprint}))
    if args.check_only:return
    env=os.environ.copy()
    env['STUDIO_CLIENT_TOKEN']=secrets.token_urlsafe(32)
    env['STUDIO_API_PORT']=str(args.api_port);env['STUDIO_UI_PORT']=str(args.ui_port)
    logs=ROOT/'.run';logs.mkdir(exist_ok=True)
    children=[];handles=[]
    try:
        for name,argv,cwd in [
            ('backend',[python,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(args.api_port)],ROOT/'backend'),
            ('frontend',[node,ROOT/'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',str(args.ui_port)],ROOT/'frontend')]:
            handle=(logs/(name+'.log')).open('w');handles.append(handle)
            children.append(subprocess.Popen([str(x) for x in argv],cwd=cwd,env=env,stdout=handle,stderr=subprocess.STDOUT,creationflags=HIDDEN))
        wait_ready(f'http://127.0.0.1:{args.api_port}/api/health',children)
        wait_ready(f'http://127.0.0.1:{args.ui_port}/api/session',children)
        print(f'Studio ready: http://127.0.0.1:{args.ui_port}. Keep this launcher running; Ctrl+C stops its children.',flush=True)
        if args.smoke_test:return
        if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{args.ui_port}')
        while all(p.poll() is None for p in children):time.sleep(0.5)
        raise RuntimeError('A Studio service exited; stopped its sibling')
    finally:
        for child in reversed(children):stop_owned(child)
        for handle in handles:handle.close()


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:pass
    except Exception as exc:
        print(f'Studio startup failed: {exc}',file=sys.stderr)
        sys.exit(1)
