from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import Capability, ParameterSpec


STUDIO_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = STUDIO_DIR.parent
STATIC_CATALOG = STUDIO_DIR / "frontend" / "src" / "data" / "capabilities.json"
PS_PUBLIC_ROOT = REPO_ROOT / "tools" / "MicrosoftFabricMgmt" / "source" / "Public"

_FUNCTION_RE = re.compile(r"^\s*function\s+([A-Za-z0-9_-]+)", re.MULTILINE | re.IGNORECASE)
_PARAM_DECL_RE = re.compile(
    r"(?P<attrs>\[Parameter(?:\([^\)]*\))?\]\s*(?:\[[^\]]+\]\s*)*)\$(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
_TYPE_RE = re.compile(
    r"\[(?P<type>(?:string|guid|int(?:32|64)?|long|bool|boolean|datetime|hashtable|object|array)(?:\[\])?|switch)\]",
    re.IGNORECASE,
)
_VALIDATE_SET_RE = re.compile(r"ValidateSet\((?P<values>[^\)]*)\)", re.IGNORECASE)
_HELP_SECTION_RE = r"^\s*\.{heading}\s*$\s*(.*?)(?=^\s*\.[A-Z][A-Z0-9_-]*(?:\s+[^\r\n]+)?\s*$|#>)"


def _risk_for_command(name: str, category: str) -> str:
    lower = name.lower()
    if category.lower() == "admin" or "asadmin" in lower:
        return "admin"
    if any(token in lower for token in ("remove-", "delete-", "drop-", "unassign-", "disconnect-")):
        return "destructive"
    if any(token in lower for token in ("new-", "set-", "update-", "add-", "create-", "assign-", "invoke-", "start-", "stop-", "resume-", "suspend-")):
        return "write"
    return "read"


def _help_section(text: str, heading: str) -> str | None:
    match = re.search(
        _HELP_SECTION_RE.format(heading=re.escape(heading)),
        text,
        flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return None
    value = " ".join(line.strip() for line in match.group(1).strip().splitlines() if line.strip())
    return value or None


def _parameter_specs(text: str) -> list[ParameterSpec]:
    specs: list[ParameterSpec] = []
    seen: set[str] = set()

    for match in _PARAM_DECL_RE.finditer(text):
        name = match.group("name")
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        attrs = match.group("attrs")

        type_matches = list(_TYPE_RE.finditer(attrs))
        parameter_type = type_matches[-1].group("type") if type_matches else "string"
        is_switch = parameter_type.lower() == "switch"
        mandatory = bool(re.search(r"Mandatory\s*=\s*\$true", attrs, flags=re.IGNORECASE))

        allowed_values: list[str] = []
        validate_set = _VALIDATE_SET_RE.search(attrs)
        if validate_set:
            raw_values = validate_set.group("values")
            allowed_values = re.findall(r"['\"]([^'\"]+)['\"]", raw_values)

        specs.append(
            ParameterSpec(
                name=name,
                type=parameter_type,
                mandatory=mandatory,
                is_switch=is_switch,
                description=_help_section(text, f"PARAMETER {name}"),
                allowed_values=allowed_values,
            )
        )

    return specs


def load_static_entries() -> list[dict[str, Any]]:
    if not STATIC_CATALOG.exists():
        return []
    raw = json.loads(STATIC_CATALOG.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Static capability catalog must be a JSON array")
    return [item for item in raw if isinstance(item, dict)]


def discover_powershell_capabilities() -> list[Capability]:
    """Discover public MicrosoftFabricMgmt commands without importing or modifying the module."""
    if not PS_PUBLIC_ROOT.exists():
        return []

    found: list[Capability] = []
    for path in sorted(PS_PUBLIC_ROOT.rglob("*.ps1")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        names = _FUNCTION_RE.findall(text)
        if not names:
            names = [path.stem]

        specs = _parameter_specs(text)
        params = [spec.name for spec in specs]
        category = path.relative_to(PS_PUBLIC_ROOT).parts[0]
        synopsis = _help_section(text, "SYNOPSIS")

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
                    description=synopsis or f"Public MicrosoftFabricMgmt command from the {category} capability group.",
                    source_path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                    generated=True,
                    parameters=params,
                    parameter_specs=specs,
                )
            )
    return found


def combined_catalog() -> list[Capability]:
    merged: dict[str, Capability] = {item.id: item for item in discover_powershell_capabilities()}

    # Curated metadata overlays generated metadata instead of replacing it, so
    # source-derived parameters and paths continue to track upstream changes.
    for entry in load_static_entries():
        entry_id = entry.get("id")
        if not entry_id:
            continue
        base = merged.get(entry_id)
        data = base.model_dump() if base else {}
        data.update(entry)
        data["generated"] = False
        merged[entry_id] = Capability.model_validate(data)

    return sorted(merged.values(), key=lambda item: (item.category.lower(), item.title.lower()))
