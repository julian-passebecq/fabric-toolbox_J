from __future__ import annotations

import importlib.util
import json
import re
import threading
from pathlib import Path
from typing import Any

from ..models import Capability, SessionStatus


STUDIO_DIR = Path(__file__).resolve().parents[3]
REPO_ROOT = STUDIO_DIR.parent
UPSTREAM_SESSION_PATH = (
    REPO_ROOT
    / "tools"
    / "MicrosoftFabricMgmtMCPServer"
    / "core"
    / "powershell_session.py"
)
_PARAM_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ProviderUnavailable(RuntimeError):
    pass


class UnsafeOperation(RuntimeError):
    pass


def _ps_literal(value: Any) -> str:
    if value is None:
        return "$null"
    if isinstance(value, bool):
        return "$true" if value else "$false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, list):
        return "@(" + ", ".join(_ps_literal(item) for item in value) + ")"
    raise ValueError(f"Unsupported PowerShell parameter type: {type(value).__name__}")


def build_read_command(capability: Capability, parameters: dict[str, Any] | None = None) -> str:
    if capability.provider != "MicrosoftFabricMgmt":
        raise UnsafeOperation("Capability is not provided by MicrosoftFabricMgmt")
    if capability.risk != "read":
        raise UnsafeOperation(f"Only read-only capabilities are enabled; risk={capability.risk}")
    if not capability.command:
        raise UnsafeOperation("Capability has no PowerShell command")

    allowed = set(capability.parameters)
    provided = parameters or {}
    unknown = sorted(set(provided) - allowed)
    if unknown:
        raise ValueError(f"Unknown parameters for {capability.command}: {', '.join(unknown)}")

    args: list[str] = []
    for key, value in provided.items():
        if value is None:
            continue
        if not _PARAM_NAME_RE.fullmatch(key):
            raise ValueError(f"Invalid parameter name: {key}")
        if isinstance(value, bool):
            if value:
                args.append(f"-{key}")
            continue
        args.append(f"-{key} {_ps_literal(value)}")

    command = " ".join(["&", _ps_literal(capability.command), *args])
    return f"{command} | ConvertTo-Json -Depth 20 -Compress"


class MicrosoftFabricMgmtRuntime:
    """Thin adapter over the upstream persistent PowerShell session implementation."""

    def __init__(self) -> None:
        self._session = None
        self._session_type = None
        self._lock = threading.Lock()
        self._connected = False
        self._tenant_id: str | None = None

    def _load_session_type(self):
        if self._session_type is not None:
            return self._session_type
        if not UPSTREAM_SESSION_PATH.exists():
            raise ProviderUnavailable(
                f"Upstream PowerShell session adapter not found: {UPSTREAM_SESSION_PATH}"
            )

        spec = importlib.util.spec_from_file_location(
            "fabric_ops_upstream_powershell_session", UPSTREAM_SESSION_PATH
        )
        if spec is None or spec.loader is None:
            raise ProviderUnavailable("Could not load upstream PowerShell session adapter")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._session_type = module.PowerShellSession
        return self._session_type

    def _get_session(self):
        with self._lock:
            if self._session is None:
                session_type = self._load_session_type()
                self._session = session_type()
            return self._session

    def connect_interactive(self, tenant_id: str) -> dict[str, Any]:
        tenant = _ps_literal(tenant_id)
        command = (
            f"Connect-FabricAccount -TenantId {tenant} | Out-Null; "
            f"[PSCustomObject]@{{ success = $true; tenant_id = {tenant}; auth = 'interactive' }} "
            "| ConvertTo-Json -Compress"
        )
        result = self.run_json(command)
        if result.get("success") is not False:
            self._connected = True
            self._tenant_id = tenant_id
        return result

    def status(self) -> SessionStatus:
        return SessionStatus(connected=self._connected, tenant_id=self._tenant_id)

    def execute_read(self, capability: Capability, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.run_json(build_read_command(capability, parameters))

    def run_json(self, command: str) -> dict[str, Any]:
        """Execute a pre-validated command through the upstream persistent PowerShell session."""
        session = self._get_session()
        raw = session.run(command)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Upstream PowerShell session returned invalid JSON") from exc
        if isinstance(parsed, dict):
            return parsed
        return {"success": True, "output": parsed}

    def close(self) -> None:
        with self._lock:
            if self._session is not None:
                self._session.close()
                self._session = None
            self._connected = False
            self._tenant_id = None


runtime = MicrosoftFabricMgmtRuntime()
