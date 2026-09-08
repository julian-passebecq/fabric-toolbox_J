import importlib.util
import socket
import subprocess
import sys

import pytest

from pathlib import Path
spec=importlib.util.spec_from_file_location('studio_launcher',Path(__file__).resolve().parents[2]/'scripts/launcher.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)


def test_native_exit_failure_is_not_ignored():
    with pytest.raises(subprocess.CalledProcessError):
        launcher.checked([sys.executable,'-c','raise SystemExit(9)'],capture_output=True)


def test_port_collision():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen()
        with pytest.raises(RuntimeError,match='occupied'):
            launcher.assert_free(listener.getsockname()[1])


def test_readiness_timeout_and_owned_cleanup():
    process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
    unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
    try:
        with pytest.raises(RuntimeError,match='deadline'):
            launcher.wait_ready('http://127.0.0.1:1',[process],timeout=0.1)
        launcher.stop_owned(process)
        assert process.poll() is not None
        assert unrelated.poll() is None
    finally:
        launcher.stop_owned(process);launcher.stop_owned(unrelated)


def test_dead_child_fails_readiness():
    process=subprocess.Popen([sys.executable,'-c','pass']);process.wait(timeout=5)
    with pytest.raises(RuntimeError,match='exited'):
        launcher.wait_ready('http://127.0.0.1:1',[process],timeout=0.1)


def test_missing_tool_is_actionable(monkeypatch):
    monkeypatch.setattr(sys,'argv',['launcher','--check-only'])
    monkeypatch.setattr(launcher.shutil,'which',lambda name:None)
    with pytest.raises(RuntimeError,match='Install Node 22'):
        launcher.main()


def test_unsupported_node_is_rejected(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(sys,'argv',['launcher','--check-only'])
    monkeypatch.setattr(launcher.shutil,'which',lambda name:name)
    monkeypatch.setattr(launcher,'checked',lambda *a,**k:SimpleNamespace(stdout='v21.7.1'))
    with pytest.raises(RuntimeError,match='requires Node'):
        launcher.main()


def test_skipinstall_rejects_unverified_dependencies(tmp_path,monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(launcher,'ROOT',tmp_path)
    monkeypatch.setattr(sys,'argv',['launcher','--skip-install','--check-only'])
    monkeypatch.setattr(launcher.shutil,'which',lambda name:name)
    monkeypatch.setattr(launcher,'checked',lambda argv,**k:SimpleNamespace(stdout='v22.22.0' if argv[0]=='node' else '7'))
    monkeypatch.setattr(launcher,'assert_free',lambda port:None)
    python=tmp_path/'backend/.venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    python.parent.mkdir(parents=True);python.touch()
    monkeypatch.setattr(launcher,'install_fingerprint',lambda:'new-lock')
    (tmp_path/'.install-state.json').write_text('{"fingerprint":"old-lock"}')
    with pytest.raises(RuntimeError,match='stale or unverified'):
        launcher.main()


def test_powershell_launcher_parses():
    path=Path(__file__).resolve().parents[2]/'scripts/start-studio.ps1'
    command="$tokens=$null;$errors=$null;[System.Management.Automation.Language.Parser]::ParseFile('"+str(path).replace("'","''")+"',[ref]$tokens,[ref]$errors)|Out-Null;if($errors.Count){exit 1}"
    launcher.checked(['pwsh','-NoProfile','-NonInteractive','-Command',command],capture_output=True)


def test_ci_covers_provider_paths_branches_and_all_lanes():
    import yaml
    root=Path(__file__).resolve().parents[3]
    workflow=yaml.load((root/'.github/workflows/studio-ci.yml').read_text(),Loader=yaml.BaseLoader)
    assert 'codex/**' in workflow['on']['push']['branches']
    for event in ['push','pull_request']:
        assert 'tools/MicrosoftFabricMgmt/**' in workflow['on'][event]['paths']
        assert 'tools/MicrosoftFabricMgmtMCPServer/**' in workflow['on'][event]['paths']
    commands='\n'.join(step.get('run','') for step in workflow['jobs']['integrated']['steps'])
    for lane in ['pytest','compileall','npm ci','npm run test -w frontend','npm run build','test:e2e','-SmokeTest']:
        assert lane in commands
