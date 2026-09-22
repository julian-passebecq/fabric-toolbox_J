from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .catalog import combined_catalog
from .models import ProjectPlan, ProjectPlanAction, ProjectPlanRequest, ProjectTemplate
from .providers.fabric_rest import execute_rest_read
from .providers.microsoftfabricmgmt import UnsafeOperation, runtime


STUDIO_DIR = Path(__file__).resolve().parents[2]
PROJECTS_DIR = STUDIO_DIR / "projects"


def list_project_templates() -> list[ProjectTemplate]:
    if not PROJECTS_DIR.exists():
        return []

    templates: list[ProjectTemplate] = []
    for path in sorted(PROJECTS_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        templates.append(ProjectTemplate.model_validate(raw))
    return templates


def get_project_template(template_id: str) -> ProjectTemplate:
    for template in list_project_templates():
        if template.id == template_id:
            return template
    raise ValueError(f"Project template not found: {template_id}")


def _items_capability():
    return next(item for item in combined_catalog() if item.id == "rest-items-list")


def _extract_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("value", "items", "data", "output"):
        value = result.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_items(value)
            if nested:
                return nested
    return []


def _live_items(workspace_id: str) -> list[dict[str, Any]]:
    session = runtime.status()
    if not session.connected:
        raise UnsafeOperation("Connect to a Fabric tenant before planning against a live workspace")
    result = execute_rest_read(_items_capability(), {"workspaceId": workspace_id})
    return _extract_items(result)


def _actual_name(item: dict[str, Any]) -> str:
    for key in ("displayName", "DisplayName", "name", "Name"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _actual_type(item: dict[str, Any]) -> str:
    for key in ("type", "Type", "itemType", "ItemType"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def plan_project(template: ProjectTemplate, request: ProjectPlanRequest) -> ProjectPlan:
    current_items = request.current_items
    live_inventory = False
    if current_items is None:
        if request.workspace_id:
            current_items = _live_items(request.workspace_id)
            live_inventory = True
        else:
            current_items = []

    actual = [item for item in current_items if isinstance(item, dict)]
    by_name_type: dict[tuple[str, str], dict[str, Any]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in actual:
        name = _actual_name(item).strip()
        item_type = _actual_type(item).strip()
        if not name:
            continue
        by_name_type[(name.casefold(), item_type.casefold())] = item
        by_name.setdefault(name.casefold(), []).append(item)

    actions: list[ProjectPlanAction] = []
    matched_actual_ids: set[int] = set()

    for desired in template.items:
        exact = by_name_type.get((desired.display_name.casefold(), desired.type.casefold()))
        if exact is not None:
            matched_actual_ids.add(id(exact))
            action = "unchanged"
            reason = "An item with the same display name and Fabric item type already exists."
        else:
            same_name = by_name.get(desired.display_name.casefold(), [])
            if same_name:
                for item in same_name:
                    matched_actual_ids.add(id(item))
                found_types = sorted({_actual_type(item) or "unknown" for item in same_name})
                action = "conflict"
                reason = "The display name is already used by another Fabric item type: " + ", ".join(found_types)
            else:
                action = "create"
                reason = "The desired item is missing from the selected workspace."

        actions.append(
            ProjectPlanAction(
                item_id=desired.id,
                display_name=desired.display_name,
                item_type=desired.type,
                area=desired.area,
                action=action,
                reason=reason,
                depends_on=desired.depends_on,
                vscode_handoff=desired.vscode_handoff,
            )
        )

    for index, item in enumerate(actual):
        if id(item) in matched_actual_ids:
            continue
        name = _actual_name(item) or f"unnamed-{index + 1}"
        item_type = _actual_type(item) or "Unknown"
        actions.append(
            ProjectPlanAction(
                item_id=str(item.get("id") or item.get("Id") or f"unmanaged-{index + 1}"),
                display_name=name,
                item_type=item_type,
                area="Existing workspace",
                action="unmanaged",
                reason="Existing Fabric item is outside this project template; Composer will not delete or modify it.",
            )
        )

    counts = Counter(action.action for action in actions)
    return ProjectPlan(
        template_id=template.id,
        project_name=template.name,
        workspace_name=template.workspace_name,
        workspace_id=request.workspace_id,
        workspace_action="use-existing" if request.workspace_id else "create",
        live_inventory=live_inventory,
        actions=actions,
        counts={key: counts.get(key, 0) for key in ("create", "unchanged", "conflict", "unmanaged")},
        apply_supported=False,
        apply_note=(
            "Project Composer is plan-only in this milestone. Item creation remains blocked until each "
            "Fabric create path is registered with the guarded-write broker and verification strategy."
        ),
    )
