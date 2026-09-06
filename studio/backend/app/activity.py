from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATA_DIR = Path.home() / ".fabric-ops-studio"
ACTIVITY_FILE = DATA_DIR / "activity.jsonl"
_LOCK = threading.Lock()
_SECRET_MARKERS = ("secret", "password", "token", "key", "credential")


def _redact(value: Any, key: str | None = None) -> Any:
    if key and any(marker in key.lower() for marker in _SECRET_MARKERS):
        return "***REDACTED***"
    if isinstance(value, dict):
        return {k: _redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def append_activity(event: dict[str, Any]) -> dict[str, Any]:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **_redact(event),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with ACTIVITY_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
    return record


def read_activity(limit: int = 200) -> list[dict[str, Any]]:
    if not ACTIVITY_FILE.exists():
        return []
    with _LOCK:
        lines = ACTIVITY_FILE.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, Any]] = []
    for line in lines[-max(1, min(limit, 1000)):]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(records))
