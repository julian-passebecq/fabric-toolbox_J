from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Capability


STUDIO_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = STUDIO_DIR.parent
STATIC_CATALOG = STUDIO_DIR / "frontend" / "src" / "data" / "capabilities.json"
PS_PUBLIC_ROOT = REPO_ROOT / "tools" / "MicrosoftFabricMgmt" / "source" / "Public"

_FUNCTION_RE = re.compile(r"^\s*function\s+([A-Za-z0-9_-]+)", re.MULTILINE | re.IGNORECASE)
_PARAM_RE = re.compile(r"\[Parameter(?:\([^\)]*\))?\]\s*(?:\[[^\]]+\]\s*)*\$([A-Za-z0-9_]+)", re.IGNORECASE)


def _risk_for_command(name: str, category: str) -> str:
    lower = name.lower()
    if category.lower() == "admin" or "admin" in lower:
        return "admin"
    if any(token in lower for token in ("remove-", "delete-", "drop-", "unassign-", "disconnect-")):
        return "destructive"
    if any(token in lower for token in ("new-", "set-", "update-", "add-", "create-", "assign-", "invoke-", "start-", "stop-", "resume-", "suspend-")):
        return "write"
    return "read"


def load_static_capabilities() -> list[Capability]:
    if not STATIC_CATALOG.exists():
        return []
    return [Capability.model_validate(item) for item in json.loads(STATIC_CATALOG.read_text(encoding="utf-8"))]


def discover_powershell_capabilities() -> list[Capability]:
    """Discover public MicrosoftFabricMgmt commands without importing or modifying the module."""
    if not PS_PUBLIC_ROOT.exists():
        return []

    found: list[Capability] = []
    for path in sorted(PS_PUBLIC_ROOT.rglob("*.ps1")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        names = _FUNCTION_RE.findall(text)
        if not names:
            # Public module files frequently use the file basename as the exported command.
            names = [path.stem]
        params = sorted(set(_PARAM_RE.findall(text)))
        category = path.relative_to(PS_PUBLIC_ROOT).parts[0]
        for name in names:
            identifier = f"ps-{category}-{name}".lower().replace(" ", "-").replace("_", "-")
            found.append(
                Capability(
                    id=identifier,
                    title=name.replace("-", " "),
                    category=category,
                    provider="MicrosoftFabricMgmt",
                    source="microsoft/fabric-toolbox",
                    risk=_risk_for_command(name, category),
                    command=name,
                    description=f"Public MicrosoftFabricMgmt command from the {category} capability group.",
                    source_path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                    generated=True,
                    parameters=params,
                )
            )
    return found


def combined_catalog() -> list[Capability]:
    merged: dict[str, Capability] = {item.id: item for item in discover_powershell_capabilities()}
    # Static entries intentionally override generated metadata for curated operations.
    for item in load_static_capabilities():
        merged[item.id] = item
    return sorted(merged.values(), key=lambda item: (item.category.lower(), item.title.lower()))
