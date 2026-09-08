from __future__ import annotations

import importlib.util
import json
import re
import threading
import math
import uuid
import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..models import Capability, SessionStatus
from ..contracts import validate_parameters
from ..admission import require_admission, source_hash
from .outcomes import normalize, wrap_invocation, OutcomeUnknown
from .session_extension import bounded_session_type
from .artifact_identity import identity_probe


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
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Non-finite numbers are unsupported')
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, list):
        return "@(" + ", ".join(_ps_literal(item) for item in value) + ")"
    raise ValueError(f"Unsupported PowerShell parameter type: {type(value).__name__}")


def _command_invocation(capability: Capability, parameters: dict[str, Any] | None = None) -> str:
    if capability.provider != "MicrosoftFabricMgmt":
        raise UnsafeOperation("Capability is not provided by MicrosoftFabricMgmt")
    if not capability.command:
        raise UnsafeOperation("Capability has no PowerShell command")

    allowed = set(capability.parameters)
    provided = validate_parameters(capability, parameters)
    unknown = sorted(set(provided) - allowed)
    if unknown:
        raise ValueError(f"Unknown parameters for {capability.command}: {', '.join(unknown)}")

    args: list[str] = []
    for key, value in provided.items():
        if value is None:
            continue
        if not _PARAM_NAME_RE.fullmatch(key):
            raise ValueError(f"Invalid parameter name: {key}")
        if next(s for s in capability.parameter_specs if s.name == key).is_switch:
            args.append(f"-{key}:{_ps_literal(value)}")
            continue
        args.append(f"-{key} {_ps_literal(value)}")

    return " ".join(["&", _ps_literal(capability.command), *args])


def build_read_command(capability: Capability, parameters: dict[str, Any] | None = None) -> str:
    require_admission(capability, 'read')
    if capability.risk != "read" or capability.execution_policy != "read":
        raise UnsafeOperation(
            f"Only registered read capabilities are enabled on the read executor; risk={capability.risk}, policy={capability.execution_policy}"
        )
    command = _command_invocation(capability, parameters)
    return wrap_invocation(command)


def build_guarded_write_command(
    capability: Capability,
    parameters: dict[str, Any] | None = None,
    *,
    what_if: bool = False,
) -> str:
    require_admission(capability, 'guarded-write')
    if capability.risk != "write" or capability.execution_policy != "guarded-write":
        raise UnsafeOperation(
            f"Capability is not allowlisted for guarded writes; risk={capability.risk}, policy={capability.execution_policy}"
        )
    command = _command_invocation(capability, parameters)

    if what_if:
        if not capability.supports_whatif:
            raise UnsafeOperation(f"{capability.command} is not registered as supporting -WhatIf")
        return wrap_invocation(f'{command} -WhatIf', 'what-if')

    return wrap_invocation(command, 'apply')


class MicrosoftFabricMgmtRuntime:
    """Thin adapter over the upstream persistent PowerShell session implementation."""

    def __init__(self) -> None:
        self._session = None
        self._session_type = None
        self._lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._generation = str(uuid.uuid4())
        self._connected = False
        self._tenant_id: str | None = None
        self._artifact_id = None
        self._transport_identity = None

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
        module.logger.disabled = True
        self._session_type = bounded_session_type(module.PowerShellSession)
        self._transport_identity = source_hash(UPSTREAM_SESSION_PATH)
        return self._session_type

    def _get_session(self):
        with self._lock:
            if self._transport_identity and self._transport_identity != source_hash(UPSTREAM_SESSION_PATH):
                raise ProviderUnavailable('Upstream transport changed; restart Studio before executing')
            if self._session is None:
                session_type = self._load_session_type()
                self._session = session_type()
            return self._session

    def _invalidate(self):
        with self._state_lock:
            self._connected = False
            self._tenant_id = None
            self._generation = str(uuid.uuid4())
            self._artifact_id = None
            return self._generation

    def connect_interactive(self, tenant_id: str) -> dict[str, Any]:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError('Tenant is required')
        generation = self._invalidate()
        with self._lock:
            if generation != self._generation:
                raise UnsafeOperation('Authentication attempt superseded')
            if self._session is not None:
                self._session.close()
                self._session = None
            command = wrap_invocation(f"Connect-FabricAccount -TenantId {_ps_literal(tenant_id)} | Out-Null", 'connect')
            try:
                result = self.run_json(command, mode='connect')
                with self._state_lock:
                    if generation != self._generation:
                        raise UnsafeOperation('Authentication attempt superseded')
                    self._connected = True
                    self._tenant_id = tenant_id
                return {**result, 'tenant_id': tenant_id, 'generation': generation}
            except Exception:
                self._invalidate()
                if self._session is not None:
                    self._session.close()
                    self._session = None
                raise

    def status(self) -> SessionStatus:
        with self._state_lock:
            session = self._session
            if self._connected and session is not None and not session._is_alive():
                self._connected = False
                self._tenant_id = None
                self._generation = str(uuid.uuid4())
            return SessionStatus(connected=self._connected, tenant_id=self._tenant_id, generation=self._generation)

    @contextmanager
    def dispatch(self, expected: SessionStatus, before_dispatch=None):
        # Lock order: session I/O -> short broker lock in callback -> state lock.
        # Broker claim always releases its lock before requesting session I/O.
        with self._lock:
            actual = self.status()
            if not actual.connected or (actual.tenant_id, actual.generation) != (expected.tenant_id, expected.generation):
                raise UnsafeOperation('Operation belongs to a different Fabric tenant/session generation')
            if before_dispatch:
                before_dispatch()
            yield

    def execute_read(self, capability, parameters=None, *, expected=None, before_dispatch=None):
        expected = expected or self.status()
        with self.dispatch(expected, before_dispatch):
            command = build_read_command(capability, parameters)
            self._check_loaded_artifact()
            return self.run_json(command)

    def execute_guarded_write(self, capability, parameters=None, *, expected=None, before_dispatch=None):
        expected = expected or self.status()
        with self.dispatch(expected):
            self._check_loaded_artifact()
            if before_dispatch:
                before_dispatch()
            return self.run_json(build_guarded_write_command(capability, parameters), mode='apply')

    def validate_guarded_write(self, capability, parameters=None, *, expected=None, before_dispatch=None):
        expected = expected or self.status()
        with self.dispatch(expected):
            self._check_loaded_artifact()
            if before_dispatch:
                before_dispatch()
            return self.run_json(build_guarded_write_command(capability, parameters, what_if=True), mode='what-if')

    def _check_loaded_artifact(self):
        source_id, command = identity_probe()
        result = self.run_json(command)
        data = result.get('data', [])
        if len(data) != 1 or not isinstance(data[0].get('module_hash'), str):
            raise UnsafeOperation('Cannot establish loaded provider identity')
        identity = (source_id, data[0]['module_hash'], self._transport_identity)
        if self._artifact_id is not None and self._artifact_id != identity:
            raise UnsafeOperation('Loaded provider identity changed; reconnect and create a new plan')
        self._artifact_id = identity

    def artifact_fingerprint(self):
        return hashlib.sha256(json.dumps(self._artifact_id).encode()).hexdigest() if self._artifact_id else ''

    def bind_artifact(self, expected):
        with self.dispatch(expected):
            self._check_loaded_artifact()
            return self.artifact_fingerprint()

    def run_json(self, command: str, *, mode: str = 'read') -> dict[str, Any]:
        with self._lock:
            try:
                session = self._get_session()
                raw = session.run(command)
            except Exception as exc:
                self._invalidate()
                if self._session is not None:
                    self._session.close()
                    self._session = None
                raise OutcomeUnknown('PowerShell transport lost; reconnect required') from exc
            try:
                return normalize(raw, mode)
            except OutcomeUnknown:
                self._invalidate()
                self._session.close()
                self._session = None
                raise

    def close(self) -> None:
        self._invalidate()
        with self._lock:
            if self._session is not None:
                self._session.close()
                self._session = None


runtime = MicrosoftFabricMgmtRuntime()
