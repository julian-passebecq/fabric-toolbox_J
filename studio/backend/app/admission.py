"""Reviewed execution manifest, independent of discovery and UI metadata."""
import hashlib
import json
from pathlib import Path

from .models import Capability

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = Path(__file__).with_name('admission.json')
WRITE_ADMISSION_SUSPENDED = True
WRITE_BLOCK_REASON = 'Guarded writes blocked pending tech-lead review: upstream retries uncertain writes and rejects HTTP 204'


def source_hash(path):
    # Git checkouts may use CRLF or LF; line endings are not semantic drift.
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n').removeprefix(b'\xef\xbb\xbf')).hexdigest()


def fingerprint(capability: Capability) -> str:
    data = capability.model_dump(exclude={'title', 'description', 'generated', 'execution_policy', 'blocked_reason', 'admission_fingerprint'})
    if capability.source_path:
        path = (ROOT / capability.source_path).resolve()
        path.relative_to(ROOT)
        data['source_sha256'] = source_hash(path)
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def apply_admission(capability: Capability) -> Capability:
    entries = json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else {}
    approved = entries.get(capability.id)
    capability.execution_policy = 'blocked'
    capability.blocked_reason = 'No reviewed execution contract'
    capability.admission_fingerprint = None
    if approved:
        try:
            actual = fingerprint(capability)
        except (OSError, ValueError):
            actual = None
        if actual == approved['fingerprint']:
            if approved['policy'] == 'guarded-write' and WRITE_ADMISSION_SUSPENDED:
                capability.blocked_reason = WRITE_BLOCK_REASON
                return capability
            capability.execution_policy = approved['policy']
            capability.admission_fingerprint = actual
            capability.blocked_reason = None
        else:
            capability.blocked_reason = 'Reviewed source or parameter contract changed; review required'
    return capability


def require_admission(capability: Capability, policy: str) -> None:
    checked = apply_admission(capability.model_copy(deep=True))
    if checked.execution_policy != policy or capability.execution_policy != policy:
        # Local import avoids coupling policy discovery to provider initialization.
        from .providers.microsoftfabricmgmt import UnsafeOperation
        raise UnsafeOperation('Capability is not allowlisted: ' + (checked.blocked_reason or 'wrong executor'))
