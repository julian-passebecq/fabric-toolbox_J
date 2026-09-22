from __future__ import annotations

import base64
import hashlib
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


def _resolve_parameters(template: ProjectTemplate, supplied: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    specs = {parameter.name: parameter for parameter in template.parameters}
    unknown = sorted(set(supplied) - set(specs))
    if unknown:
        raise ValueError("Unknown project parameters: " + ", ".join(unknown))

    resolved: dict[str, Any] = {}
    missing: list[str] = []
    for parameter in template.parameters:
        value = supplied.get(parameter.name, parameter.default)
        if parameter.required and value in (None, ""):
            missing.append(parameter.name)
        if parameter.allowed_values and value not in (None, "") and str(value) not in parameter.allowed_values:
            allowed = ", ".join(parameter.allowed_values)
            raise ValueError(f"Invalid value for {parameter.name}; allowed values: {allowed}")
        if parameter.secret and value not in (None, ""):
            resolved[parameter.name] = "***"
        else:
            resolved[parameter.name] = value
    return resolved, missing


PROVISIONERS: dict[str, dict[str, str]] = {
    "Eventhouse": {
        "capability_id": "ps-eventhouse-new-fabriceventhouse",
        "name_parameter": "EventhouseName",
        "description_parameter": "EventhouseDescription",
    },
    "Eventstream": {
        "capability_id": "ps-eventstream-new-fabriceventstream",
        "name_parameter": "EventstreamName",
        "description_parameter": "EventstreamDescription",
    },
    "KQLDatabase": {
        "capability_id": "ps-kql-database-new-fabrickqldatabase",
        "name_parameter": "KQLDatabaseName",
        "description_parameter": "KQLDatabaseDescription",
    },
    "KQLQueryset": {
        "capability_id": "ps-kql-queryset-new-fabrickqlqueryset",
        "name_parameter": "KQLQuerysetName",
        "description_parameter": "KQLQuerysetDescription",
    },
    "KQLDashboard": {
        "capability_id": "ps-kql-dashboard-new-fabrickqldashboard",
        "name_parameter": "KQLDashboardName",
        "description_parameter": "KQLDashboardDescription",
    },
    "Lakehouse": {
        "capability_id": "ps-lakehouse-new-fabriclakehouse",
        "name_parameter": "LakehouseName",
        "description_parameter": "LakehouseDescription",
    },
    "Notebook": {
        "capability_id": "ps-notebook-new-fabricnotebook",
        "name_parameter": "NotebookName",
        "description_parameter": "NotebookDescription",
    },
    "Environment": {
        "capability_id": "ps-environment-new-fabricenvironment",
        "name_parameter": "EnvironmentName",
        "description_parameter": "EnvironmentDescription",
    },
    "DataPipeline": {
        "capability_id": "ps-data-pipeline-new-fabricdatapipeline",
        "name_parameter": "DataPipelineName",
        "description_parameter": "DataPipelineDescription",
    },
}


def _actual_id(item: dict[str, Any] | None) -> str:
    if not item:
        return ""
    for key in ("id", "Id", "itemId", "ItemId"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _provisioning_for(
    desired,
    action: str,
    request: ProjectPlanRequest,
    existing_by_template_id: dict[str, dict[str, Any]],
    catalog_by_id: dict[str, Any],
) -> tuple[str | None, dict[str, Any], bool, str]:
    if action != "create":
        if action == "unchanged":
            return None, {}, False, "The item already exists; no create plan is needed."
        if action == "conflict":
            return None, {}, False, "Resolve the display-name/type conflict before provisioning."
        return None, {}, False, "Unmanaged workspace items are never provisioned by this template."

    provisioner = PROVISIONERS.get(desired.type)
    if not provisioner:
        return None, {}, False, f"No reviewed guarded create capability is registered for {desired.type}."

    capability_id = provisioner["capability_id"]
    capability = catalog_by_id.get(capability_id)
    if not capability or capability.execution_policy != "guarded-write":
        return capability_id, {}, False, "The required create capability is not currently guarded-write enabled."

    if not request.workspace_id:
        return capability_id, {}, False, "Create or select the target workspace before staging item creates."

    missing_dependencies = [dependency for dependency in desired.depends_on if dependency not in existing_by_template_id]
    if missing_dependencies:
        return (
            capability_id,
            {},
            False,
            "Create and verify dependencies first, then refresh the project plan: "
            + ", ".join(missing_dependencies),
        )

    parameters: dict[str, Any] = {
        "WorkspaceId": request.workspace_id,
        provisioner["name_parameter"]: desired.display_name,
    }
    if desired.description:
        parameters[provisioner["description_parameter"]] = desired.description[:256]

    if desired.type == "KQLDatabase":
        parent_ref = str(desired.settings.get("parentEventhouseRef") or "")
        if not parent_ref:
            parent_ref = next(
                (
                    dependency
                    for dependency in desired.depends_on
                    if dependency in existing_by_template_id
                    and _actual_type(existing_by_template_id[dependency]).casefold() == "eventhouse"
                ),
                "",
            )
        parent_id = _actual_id(existing_by_template_id.get(parent_ref)) if parent_ref else ""
        if not parent_id:
            return (
                capability_id,
                {},
                False,
                "The parent Eventhouse exists logically but its Fabric item ID could not be resolved.",
            )
        parameters["parentEventhouseId"] = parent_id
        parameters["KQLDatabaseType"] = str(desired.settings.get("databaseType") or "ReadWrite")

    return (
        capability_id,
        parameters,
        True,
        "Ready to stage as a guarded mutation plan. Execution still requires -WhatIf validation and typed approval.",
    )


def plan_project(template: ProjectTemplate, request: ProjectPlanRequest) -> ProjectPlan:
    resolved_parameters, missing_parameters = _resolve_parameters(template, request.parameters)
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

    desired_status: list[tuple[Any, str, str, dict[str, Any] | None]] = []
    existing_by_template_id: dict[str, dict[str, Any]] = {}
    matched_actual_ids: set[int] = set()

    for desired in template.items:
        exact = by_name_type.get((desired.display_name.casefold(), desired.type.casefold()))
        if exact is not None:
            matched_actual_ids.add(id(exact))
            existing_by_template_id[desired.id] = exact
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
        desired_status.append((desired, action, reason, exact))

    catalog_by_id = {item.id: item for item in combined_catalog()}
    actions: list[ProjectPlanAction] = []
    for desired, action, reason, _ in desired_status:
        capability_id, provisioning_parameters, provisioning_ready, provisioning_reason = _provisioning_for(
            desired,
            action,
            request,
            existing_by_template_id,
            catalog_by_id,
        )
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
                provisioning_capability_id=capability_id,
                provisioning_parameters=provisioning_parameters,
                provisioning_ready=provisioning_ready,
                provisioning_reason=provisioning_reason,
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
                provisioning_reason="Unmanaged workspace items are preserved and never changed by Composer.",
            )
        )

    counts = Counter(action.action for action in actions)
    ready_count = sum(1 for action in actions if action.provisioning_ready)
    return ProjectPlan(
        template_id=template.id,
        project_name=template.name,
        workspace_name=template.workspace_name,
        workspace_id=request.workspace_id,
        workspace_action="use-existing" if request.workspace_id else "create",
        live_inventory=live_inventory,
        actions=actions,
        counts={key: counts.get(key, 0) for key in ("create", "unchanged", "conflict", "unmanaged")},
        resolved_parameters=resolved_parameters,
        missing_parameters=missing_parameters,
        apply_supported=False,
        apply_note=(
            ("Missing required project parameters: " + ", ".join(missing_parameters) + ". ")
            if missing_parameters
            else ""
        )
        + (
            f"{ready_count} create action(s) are ready to stage as guarded mutation plans. "
            "Composer stages only resources whose dependencies already exist in Fabric; execute each staged plan "
            "through Change Plans with upstream -WhatIf validation and typed approval, then refresh Composer for the next wave."
            if ready_count
            else
            "No create action is dependency-ready yet. Create/select the workspace or execute the previous dependency wave, then refresh the plan."
        ),
    )


def build_eventstream_definition(template: ProjectTemplate, request: ProjectPlanRequest) -> dict[str, Any]:
    """Render the Foil'o Eventstream topology from project parameters and resolved Fabric dependencies."""
    resolved_parameters, missing_parameters = _resolve_parameters(template, request.parameters)
    current_items = request.current_items
    live_inventory = False
    if current_items is None:
        if request.workspace_id:
            current_items = _live_items(request.workspace_id)
            live_inventory = True
        else:
            current_items = []

    actual = [item for item in current_items if isinstance(item, dict)]
    by_name_type = {
        (_actual_name(item).strip().casefold(), _actual_type(item).strip().casefold()): item
        for item in actual
        if _actual_name(item).strip()
    }

    eventstream = next((item for item in template.items if item.type == "Eventstream"), None)
    eventhouse = next((item for item in template.items if item.type == "Eventhouse"), None)
    database = next((item for item in template.items if item.type == "KQLDatabase"), None)
    if not eventstream or not eventhouse or not database:
        raise ValueError("Project template must declare Eventstream, Eventhouse and KQLDatabase items")

    existing_eventhouse = by_name_type.get((eventhouse.display_name.casefold(), "eventhouse"))
    existing_database = by_name_type.get((database.display_name.casefold(), "kqldatabase"))
    eventhouse_id = _actual_id(existing_eventhouse)

    mode = str(resolved_parameters.get("ingestion_mode") or "fabric-kafka-endpoint")
    topic = str(resolved_parameters.get("kafka_topic") or "foil.wind.telemetry")
    consumer_group = str(resolved_parameters.get("kafka_consumer_group") or "foilo-fabric-consumer")
    connection_id = str(resolved_parameters.get("kafka_connection_id") or "")
    table_name = str(resolved_parameters.get("kql_table_name") or "turbine_telemetry")

    missing_requirements = list(missing_parameters)
    if not request.workspace_id:
        missing_requirements.append("workspace_id")
    if not eventhouse_id:
        missing_requirements.append("eventhouse_item_id")
    if not existing_database:
        missing_requirements.append("kql_database_item")
    if mode == "direct-kafka-source" and not connection_id:
        missing_requirements.append("kafka_connection_id")

    source_name = "foilo-kafka-ingress"
    stream_name = "wind-events-stream"

    if mode == "fabric-kafka-endpoint":
        source = {
            "name": source_name,
            "type": "CustomEndpoint",
            "properties": {},
        }
    elif mode == "direct-kafka-source":
        source = {
            "name": source_name,
            "type": "ApacheKafka",
            "properties": {
                "dataConnectionId": connection_id,
                "topic": topic,
                "consumerGroupName": consumer_group,
                "autoOffsetReset": "Latest",
                "saslMechanism": "PLAIN",
                "securityProtocol": "SASL_SSL",
            },
        }
    else:
        raise ValueError(f"Unsupported Eventstream ingestion mode: {mode}")

    definition = {
        "sources": [source],
        "destinations": [
            {
                "name": "foilo-eventhouse-destination",
                "type": "Eventhouse",
                "properties": {
                    "dataIngestionMode": "ProcessedIngestion",
                    "workspaceId": request.workspace_id or "",
                    "itemId": eventhouse_id,
                    "databaseName": database.display_name,
                    "tableName": table_name,
                    "inputSerialization": {
                        "type": "Json",
                        "properties": {"encoding": "UTF8"},
                    },
                },
                "inputNodes": [{"name": stream_name}],
            }
        ],
        "streams": [
            {
                "name": stream_name,
                "type": "DefaultStream",
                "properties": {},
                "inputNodes": [{"name": source_name}],
            }
        ],
        "operators": [],
        "compatibilityLevel": "1.1",
    }

    return {
        "template_id": template.id,
        "item_id": eventstream.id,
        "display_name": eventstream.display_name,
        "filename": "eventstream.json",
        "ready": not missing_requirements,
        "missing_requirements": sorted(set(missing_requirements)),
        "live_inventory": live_inventory,
        "source_mode": mode,
        "definition": definition,
        "provenance": {
            "schema": "Microsoft Fabric Eventstream definition",
            "source": "Microsoft Fabric REST API",
        },
    }


def _eventstream_definition_capability():
    return next(
        item
        for item in combined_catalog()
        if item.id == "rest-eventstream-definition-get"
    )


def _find_definition_parts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        definition = value.get("definition")
        if isinstance(definition, dict) and isinstance(definition.get("parts"), list):
            return [part for part in definition["parts"] if isinstance(part, dict)]
        for child in value.values():
            parts = _find_definition_parts(child)
            if parts:
                return parts
    elif isinstance(value, list):
        for child in value:
            parts = _find_definition_parts(child)
            if parts:
                return parts
    return []


def _decode_eventstream_definition(result: dict[str, Any]) -> dict[str, Any]:
    parts = _find_definition_parts(result)
    part = next((item for item in parts if item.get("path") == "eventstream.json"), None)
    if not part:
        raise ValueError("Fabric getDefinition response did not contain eventstream.json")

    payload = part.get("payload")
    if not isinstance(payload, str) or not payload:
        raise ValueError("Fabric eventstream.json definition payload is empty")

    try:
        decoded = base64.b64decode(payload, validate=True).decode("utf-8-sig")
        parsed = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Fabric eventstream.json payload is not valid Base64 JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Fabric eventstream.json payload must decode to a JSON object")
    return parsed


def _semantic_definition(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _semantic_definition(child)
            for key, child in sorted(value.items())
            if key != "id"
        }
    if isinstance(value, list):
        return [_semantic_definition(child) for child in value]
    return value


def _definition_digest(value: Any) -> str:
    canonical = json.dumps(
        _semantic_definition(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _definition_diff(desired: Any, actual: Any, path: str = "$", limit: int = 50) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []

    def walk(expected: Any, current: Any, current_path: str) -> None:
        if len(differences) >= limit:
            return

        if isinstance(expected, dict) and isinstance(current, dict):
            keys = sorted(set(expected) | set(current))
            for key in keys:
                if key == "id":
                    continue
                next_path = f"{current_path}.{key}"
                if key not in expected:
                    differences.append(
                        {"path": next_path, "kind": "extra", "desired": None, "actual": current[key]}
                    )
                elif key not in current:
                    differences.append(
                        {"path": next_path, "kind": "missing", "desired": expected[key], "actual": None}
                    )
                else:
                    walk(expected[key], current[key], next_path)
                if len(differences) >= limit:
                    return
            return

        if isinstance(expected, list) and isinstance(current, list):
            if len(expected) != len(current):
                differences.append(
                    {
                        "path": current_path,
                        "kind": "length",
                        "desired": len(expected),
                        "actual": len(current),
                    }
                )
            for index, (expected_item, current_item) in enumerate(zip(expected, current)):
                walk(expected_item, current_item, f"{current_path}[{index}]")
                if len(differences) >= limit:
                    return
            return

        if expected != current:
            differences.append(
                {
                    "path": current_path,
                    "kind": "changed",
                    "desired": expected,
                    "actual": current,
                }
            )

    walk(_semantic_definition(desired), _semantic_definition(actual), path)
    return differences


def inspect_eventstream_drift(template: ProjectTemplate, request: ProjectPlanRequest) -> dict[str, Any]:
    """Compare the desired Composer Eventstream topology with the current Fabric definition."""
    if not request.workspace_id:
        return {
            "template_id": template.id,
            "ready": False,
            "in_sync": False,
            "missing_requirements": ["workspace_id"],
            "differences": [],
        }

    current_items = request.current_items
    live_inventory = False
    if current_items is None:
        current_items = _live_items(request.workspace_id)
        live_inventory = True

    actual = [item for item in current_items if isinstance(item, dict)]
    by_name_type = {
        (_actual_name(item).strip().casefold(), _actual_type(item).strip().casefold()): item
        for item in actual
        if _actual_name(item).strip()
    }

    eventstream = next((item for item in template.items if item.type == "Eventstream"), None)
    if not eventstream:
        raise ValueError("Project template must declare an Eventstream item")

    existing_eventstream = by_name_type.get((eventstream.display_name.casefold(), "eventstream"))
    eventstream_id = _actual_id(existing_eventstream)
    if not eventstream_id:
        return {
            "template_id": template.id,
            "display_name": eventstream.display_name,
            "workspace_id": request.workspace_id,
            "ready": False,
            "in_sync": False,
            "live_inventory": live_inventory,
            "missing_requirements": ["eventstream_item"],
            "differences": [],
        }

    desired_request = ProjectPlanRequest(
        workspace_id=request.workspace_id,
        current_items=actual,
        parameters=request.parameters,
    )
    artifact = build_eventstream_definition(template, desired_request)
    if not artifact["ready"]:
        return {
            "template_id": template.id,
            "display_name": eventstream.display_name,
            "workspace_id": request.workspace_id,
            "eventstream_id": eventstream_id,
            "ready": False,
            "in_sync": False,
            "live_inventory": live_inventory,
            "missing_requirements": artifact["missing_requirements"],
            "differences": [],
        }

    result = execute_rest_read(
        _eventstream_definition_capability(),
        {
            "workspaceId": request.workspace_id,
            "eventstreamId": eventstream_id,
        },
    )
    live_definition = _decode_eventstream_definition(result)
    desired_definition = artifact["definition"]

    desired_sha256 = _definition_digest(desired_definition)
    live_sha256 = _definition_digest(live_definition)
    differences = _definition_diff(desired_definition, live_definition)

    return {
        "template_id": template.id,
        "display_name": eventstream.display_name,
        "workspace_id": request.workspace_id,
        "eventstream_id": eventstream_id,
        "ready": True,
        "in_sync": desired_sha256 == live_sha256,
        "live_inventory": live_inventory,
        "missing_requirements": [],
        "desired_sha256": desired_sha256,
        "live_sha256": live_sha256,
        "difference_count": len(differences),
        "differences": differences,
        "desired_definition": desired_definition,
        "live_definition": live_definition,
        "comparison": "semantic topology; Fabric-generated id fields are ignored",
    }
