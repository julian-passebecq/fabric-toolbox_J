"""Narrow lifecycle extension: retain upstream framing/import/domain transport.

The watchdog kills the owned process to unblock upstream's blocking readline.
It is joined before returning; no timed-out invocation continues in a worker.
"""
import os
import subprocess
import threading


class CommandInput:
    """PowerShell stdin command mode needs a blank line after compound statements."""
    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        return self.stream.write(text + '\n')

    def flush(self):
        return self.stream.flush()

    def close(self):
        return self.stream.close()


def bounded_session_type(base):
    class BoundedSession(base):
        def _start(self):
            if getattr(self, '_studio_started', False):
                raise RuntimeError('Implicit PowerShell restart is prohibited')
            self._studio_started = True
            try:
                # Upstream starts an interactive REPL even with redirected stdin.
                # Retain its run/framing/parser, but explicitly select stdin command
                # mode and terminate compound input. No domain command is replaced.
                env = os.environ.copy()
                env['TERM'] = 'dumb'
                self._process = subprocess.Popen(
                    ['pwsh','-NoProfile','-NonInteractive','-NoLogo','-ExecutionPolicy','RemoteSigned','-Command','-'],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding='utf-8', bufsize=1, env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,
                )
                self._process.stdin = CommandInput(self._process.stdin)
                self._stderr_thread = threading.Thread(target=self._drain_stderr,daemon=True,name='studio-pwsh-stderr')
                self._stderr_thread.start()
                path = str(self._module_path).replace("'", "''")
                self._process.stdin.write(
                    "$ErrorActionPreference='Stop'; $WarningPreference='SilentlyContinue'; "
                    "$ProgressPreference='SilentlyContinue'; $InformationPreference='SilentlyContinue'; "
                    f"try {{ Import-Module '{path}' -Force; Write-Output '__MGMT_DONE__:0' }} "
                    "catch { Write-Output '__MGMT_DONE__:1' }\n"
                )
                self._process.stdin.flush()
                _, exit_code = self._read_until_sentinel()
                if exit_code != 0:
                    raise RuntimeError('Provider module import failed')
            except BaseException:
                self.close()
                raise

        def _read_until_sentinel(self):
            process = self._process
            expired = threading.Event()

            def stop():
                expired.set()
                self._kill_owned(process)

            timer = threading.Timer(self._timeout, stop)
            timer.start()
            try:
                result = super()._read_until_sentinel()
                if expired.is_set():
                    raise TimeoutError('PowerShell invocation deadline exceeded')
                return result
            finally:
                timer.cancel()
                timer.join()
                if expired.is_set():
                    self.close()

        @staticmethod
        def _kill_owned(process):
            if process is not None and process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)

        def run(self, command):
            if not self._is_alive():
                raise RuntimeError('PowerShell session lost; explicit reconnect required')
            return super().run(command)

        def close(self):
            process = getattr(self, '_process', None)
            self._kill_owned(process)
            worker = getattr(self, '_stderr_thread', None)
            if worker is not None and worker is not threading.current_thread():
                worker.join(timeout=10)
                if worker.is_alive():
                    raise RuntimeError('PowerShell stream worker did not stop')
            if process is not None:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
            self._process = None
    return BoundedSession
