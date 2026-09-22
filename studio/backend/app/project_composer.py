from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .catalog import combined_catalog
from .models import (
    ProjectAcceptanceCheck,
    ProjectAcceptanceReport,
    ProjectPlan,
    ProjectPlanAction,
    ProjectPlanRequest,
    ProjectTemplate,
    ProjectWaveStageEntry,
    ProjectWaveStageIssue,
    ProjectWaveStageResult,
    MutationArtifactRequest,
)
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



def _reconciliation_for(
    desired,
    action: str,
    request: ProjectPlanRequest,
    existing_item: dict[str, Any] | None,
    existing_by_template_id: dict[str, dict[str, Any]],
    catalog_by_id: dict[str, Any],
) -> tuple[str | None, dict[str, Any], bool, str]:
    if desired.type != "Eventstream":
        return None, {}, False, ""
    if action != "unchanged" or not existing_item:
        return None, {}, False, "Definition reconciliation becomes available after the Eventstream exists in Fabric."

    capability_id = "ps-eventstream-update-fabriceventstreamdefinition"
    capability = catalog_by_id.get(capability_id)
    if not capability or capability.execution_policy != "guarded-write":
        return capability_id, {}, False, "The reviewed Eventstream definition update capability is not enabled."

    if not request.workspace_id:
        return capability_id, {}, False, "Select the live workspace before reconciling an Eventstream definition."

    eventstream_id = _actual_id(existing_item)
    if not eventstream_id:
        return capability_id, {}, False, "The existing Eventstream item ID could not be resolved."

    missing_dependencies = [
        dependency for dependency in desired.depends_on
        if dependency not in existing_by_template_id
    ]
    if missing_dependencies:
        return (
            capability_id,
            {},
            False,
            "Definition reconciliation requires the declared Fabric dependencies first: "
            + ", ".join(missing_dependencies),
        )

    return (
        capability_id,
        {
            "WorkspaceId": request.workspace_id,
            "EventstreamId": eventstream_id,
        },
        True,
        "Existing Eventstream can be reconciled to the generated project definition through a guarded, artifact-bound Change Plan.",
    )



def _deployment_wave_map(template: ProjectTemplate) -> dict[str, int]:
    by_id = {item.id: item for item in template.items}
    cache: dict[str, int] = {}

    def resolve(item_id: str, stack: tuple[str, ...] = ()) -> int:
        if item_id in cache:
            return cache[item_id]
        if item_id in stack:
            cycle = " -> ".join((*stack, item_id))
            raise ValueError(f"Project template dependency cycle: {cycle}")

        item = by_id.get(item_id)
        if not item:
            raise ValueError(f"Project template dependency not found: {item_id}")

        if not item.depends_on:
            wave = 1
        else:
            dependency_waves: list[int] = []
            for dependency in item.depends_on:
                if dependency not in by_id:
                    raise ValueError(
                        f"Project item {item.id} depends on unknown template item {dependency}"
                    )
                dependency_waves.append(resolve(dependency, (*stack, item_id)))
            wave = max(dependency_waves) + 1

        cache[item_id] = wave
        return wave

    for item_id in by_id:
        resolve(item_id)
    return cache


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
    wave_by_id = _deployment_wave_map(template)
    actions: list[ProjectPlanAction] = []
    for desired, action, reason, existing_item in desired_status:
        capability_id, provisioning_parameters, provisioning_ready, provisioning_reason = _provisioning_for(
            desired,
            action,
            request,
            existing_by_template_id,
            catalog_by_id,
        )
        (
            reconciliation_capability_id,
            reconciliation_parameters,
            reconciliation_ready,
            reconciliation_reason,
        ) = _reconciliation_for(
            desired,
            action,
            request,
            existing_item,
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
                reconciliation_capability_id=reconciliation_capability_id,
                reconciliation_parameters=reconciliation_parameters,
                reconciliation_ready=reconciliation_ready,
                reconciliation_reason=reconciliation_reason,
                deployment_wave=wave_by_id.get(desired.id),
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
    blocking_waves = [
        action.deployment_wave
        for action in actions
        if action.action in {"create", "conflict"} and action.deployment_wave is not None
    ]
    current_wave = min(blocking_waves) if blocking_waves else None
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
        current_wave=current_wave,
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


def _canonical_json(value: Any, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonical_json(value[key], key)
            for key in sorted(value)
        }
    if isinstance(value, list):
        canonical = [_canonical_json(item) for item in value]
        if parent_key in {"sources", "destinations", "streams", "operators"}:
            return sorted(
                canonical,
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            )
        return canonical
    return value


def _json_sha256(value: Any) -> str:
    payload = json.dumps(
        _canonical_json(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _find_eventstream_part(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if value.get("path") == "eventstream.json" and "payload" in value:
            return value
        for nested in value.values():
            found = _find_eventstream_part(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_eventstream_part(nested)
            if found:
                return found
    return None


def _decode_eventstream_definition(result: dict[str, Any]) -> dict[str, Any]:
    part = _find_eventstream_part(result)
    if not part:
        raise ValueError("Live Eventstream definition did not contain eventstream.json")

    payload = part.get("payload")
    if not isinstance(payload, str) or not payload:
        raise ValueError("Live Eventstream eventstream.json payload is empty")

    payload_type = str(part.get("payloadType") or "")
    try:
        if payload_type.casefold() == "inlinebase64":
            decoded = base64.b64decode(payload, validate=True).decode("utf-8-sig")
        else:
            decoded = payload
        parsed = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError("Live Eventstream eventstream.json payload could not be decoded") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Live Eventstream definition must decode to a JSON object")
    return parsed


def accept_project(template: ProjectTemplate, request: ProjectPlanRequest) -> ProjectAcceptanceReport:
    if not request.workspace_id:
        raise ValueError("workspace_id is required for deployment acceptance")

    resolved_parameters, missing_parameters = _resolve_parameters(template, request.parameters)
    del resolved_parameters

    current_items = request.current_items
    if current_items is None:
        current_items = _live_items(request.workspace_id)
    actual = [item for item in current_items if isinstance(item, dict)]

    by_name_type = {
        (_actual_name(item).strip().casefold(), _actual_type(item).strip().casefold()): item
        for item in actual
        if _actual_name(item).strip()
    }
    desired_by_id = {item.id: item for item in template.items}

    checks: list[ProjectAcceptanceCheck] = []
    required_chain = [
        ("rti-eventhouse", "Eventhouse"),
        ("rti-kql-database", "KQL Database"),
        ("rti-eventstream", "Eventstream"),
        ("de-lakehouse", "Lakehouse"),
    ]
    existing_by_template_id: dict[str, dict[str, Any]] = {}

    for template_item_id, label in required_chain:
        desired = desired_by_id.get(template_item_id)
        if not desired:
            checks.append(
                ProjectAcceptanceCheck(
                    id=f"item:{template_item_id}",
                    label=label,
                    status="fail",
                    detail="Required acceptance item is missing from the project template.",
                )
            )
            continue

        existing = by_name_type.get((desired.display_name.casefold(), desired.type.casefold()))
        if existing:
            existing_by_template_id[template_item_id] = existing
            checks.append(
                ProjectAcceptanceCheck(
                    id=f"item:{template_item_id}",
                    label=label,
                    status="pass",
                    detail=f"{desired.display_name} exists with the expected Fabric item type.",
                    item_id=_actual_id(existing) or None,
                    expected=f"{desired.type}:{desired.display_name}",
                    actual=f"{_actual_type(existing)}:{_actual_name(existing)}",
                )
            )
        else:
            checks.append(
                ProjectAcceptanceCheck(
                    id=f"item:{template_item_id}",
                    label=label,
                    status="fail",
                    detail=f"{desired.display_name} is missing from the selected workspace.",
                    expected=f"{desired.type}:{desired.display_name}",
                )
            )

    if missing_parameters:
        checks.append(
            ProjectAcceptanceCheck(
                id="parameters",
                label="Project parameters",
                status="fail",
                detail="Required project parameters are missing: " + ", ".join(missing_parameters),
            )
        )
    else:
        checks.append(
            ProjectAcceptanceCheck(
                id="parameters",
                label="Project parameters",
                status="pass",
                detail="Required Foil'o project parameters are resolved.",
            )
        )

    desired_hash: str | None = None
    live_hash: str | None = None
    definition_match: bool | None = None

    eventstream = existing_by_template_id.get("rti-eventstream")
    dependencies_ready = all(
        key in existing_by_template_id
        for key in ("rti-eventhouse", "rti-kql-database", "rti-eventstream")
    )

    if eventstream and dependencies_ready and not missing_parameters:
        artifact_request = ProjectPlanRequest(
            workspace_id=request.workspace_id,
            current_items=actual,
            parameters=request.parameters,
        )
        artifact = build_eventstream_definition(template, artifact_request)
        if not artifact["ready"]:
            checks.append(
                ProjectAcceptanceCheck(
                    id="eventstream-definition",
                    label="Eventstream topology",
                    status="fail",
                    detail="Desired Eventstream definition is not renderable: "
                    + ", ".join(artifact["missing_requirements"]),
                )
            )
        else:
            desired_definition = artifact["definition"]
            desired_hash = _json_sha256(desired_definition)
            capability = next(
                (
                    item
                    for item in combined_catalog()
                    if item.id == "ps-eventstream-get-fabriceventstreamdefinition"
                ),
                None,
            )
            if not capability or capability.execution_policy != "read":
                checks.append(
                    ProjectAcceptanceCheck(
                        id="eventstream-definition",
                        label="Eventstream topology",
                        status="fail",
                        detail="Reviewed Eventstream definition read capability is unavailable.",
                        expected=desired_hash,
                    )
                )
            else:
                eventstream_id = _actual_id(eventstream)
                try:
                    live_result = runtime.execute_read(
                        capability,
                        {
                            "WorkspaceId": request.workspace_id,
                            "EventstreamId": eventstream_id,
                        },
                    )
                    live_definition = _decode_eventstream_definition(live_result)
                    live_hash = _json_sha256(live_definition)
                    definition_match = desired_hash == live_hash
                    checks.append(
                        ProjectAcceptanceCheck(
                            id="eventstream-definition",
                            label="Eventstream topology",
                            status="pass" if definition_match else "fail",
                            detail=(
                                "Live eventstream.json matches the generated Foil'o topology."
                                if definition_match
                                else "Live eventstream.json differs from the generated Foil'o topology; stage definition reconciliation."
                            ),
                            item_id=eventstream_id or None,
                            expected=desired_hash,
                            actual=live_hash,
                        )
                    )
                except (ValueError, RuntimeError) as exc:
                    checks.append(
                        ProjectAcceptanceCheck(
                            id="eventstream-definition",
                            label="Eventstream topology",
                            status="fail",
                            detail=f"Live Eventstream definition could not be verified: {exc}",
                            item_id=eventstream_id or None,
                            expected=desired_hash,
                        )
                    )
    else:
        missing = [
            key
            for key in ("rti-eventhouse", "rti-kql-database", "rti-eventstream")
            if key not in existing_by_template_id
        ]
        checks.append(
            ProjectAcceptanceCheck(
                id="eventstream-definition",
                label="Eventstream topology",
                status="fail",
                detail=(
                    "Topology comparison is blocked until required Fabric items exist: "
                    + ", ".join(missing)
                    if missing
                    else "Topology comparison is blocked until required project parameters are resolved."
                ),
            )
        )

    accepted = all(check.status == "pass" for check in checks)
    return ProjectAcceptanceReport(
        template_id=template.id,
        project_name=template.name,
        workspace_id=request.workspace_id,
        status="pass" if accepted else "fail",
        accepted=accepted,
        checks=checks,
        desired_eventstream_sha256=desired_hash,
        live_eventstream_sha256=live_hash,
        definition_match=definition_match,
    )


def stage_project_wave(
    template: ProjectTemplate,
    request: ProjectPlanRequest,
    mutation_broker=None,
) -> ProjectWaveStageResult:
    if not request.workspace_id:
        raise ValueError("workspace_id is required to stage a deployment wave")

    if mutation_broker is None:
        from .mutations import broker as mutation_broker

    current_items = request.current_items
    if current_items is None:
        current_items = _live_items(request.workspace_id)

    snapshot = ProjectPlanRequest(
        workspace_id=request.workspace_id,
        current_items=current_items,
        parameters=request.parameters,
    )
    plan = plan_project(template, snapshot)

    if plan.missing_parameters:
        return ProjectWaveStageResult(
            template_id=template.id,
            project_name=template.name,
            workspace_id=request.workspace_id,
            wave=plan.current_wave,
            status="blocked",
            issues=[
                ProjectWaveStageIssue(
                    item_id="project-parameters",
                    display_name="Project parameters",
                    detail="Missing required project parameters: " + ", ".join(plan.missing_parameters),
                )
            ],
            note="Resolve project parameters before staging the current deployment wave.",
        )

    if plan.current_wave is None:
        return ProjectWaveStageResult(
            template_id=template.id,
            project_name=template.name,
            workspace_id=request.workspace_id,
            status="complete",
            note="No create/conflict deployment wave remains in the project plan.",
        )

    candidates = [
        action
        for action in plan.actions
        if action.action == "create"
        and action.deployment_wave == plan.current_wave
        and action.provisioning_ready
        and action.provisioning_capability_id
    ]

    if not candidates:
        blockers = [
            action
            for action in plan.actions
            if action.deployment_wave == plan.current_wave
            and action.action in {"create", "conflict"}
        ]
        return ProjectWaveStageResult(
            template_id=template.id,
            project_name=template.name,
            workspace_id=request.workspace_id,
            wave=plan.current_wave,
            status="blocked",
            issues=[
                ProjectWaveStageIssue(
                    item_id=action.item_id,
                    display_name=action.display_name,
                    detail=(
                        action.reason
                        if action.action == "conflict"
                        else action.provisioning_reason or action.reason
                    ),
                )
                for action in blockers
            ],
            note=f"Deployment wave {plan.current_wave} has no dependency-ready create actions.",
        )

    catalog_by_id = {item.id: item for item in combined_catalog()}
    staged: list[ProjectWaveStageEntry] = []
    issues: list[ProjectWaveStageIssue] = []

    for action in candidates:
        capability = catalog_by_id.get(action.provisioning_capability_id or "")
        if not capability:
            issues.append(
                ProjectWaveStageIssue(
                    item_id=action.item_id,
                    display_name=action.display_name,
                    detail="Provisioning capability is missing from the current catalog.",
                )
            )
            continue

        artifacts: list[MutationArtifactRequest] = []
        if action.item_type == "Eventstream":
            artifact = build_eventstream_definition(template, snapshot)
            if not artifact["ready"]:
                issues.append(
                    ProjectWaveStageIssue(
                        item_id=action.item_id,
                        display_name=action.display_name,
                        detail="Eventstream definition is not ready: "
                        + ", ".join(artifact["missing_requirements"]),
                    )
                )
                continue
            artifacts.append(
                MutationArtifactRequest(
                    parameter="EventstreamPathDefinition",
                    filename=artifact["filename"],
                    content=json.dumps(artifact["definition"], indent=2, sort_keys=True),
                )
            )

        try:
            mutation_plan = mutation_broker.create_plan(
                capability,
                action.provisioning_parameters,
                artifacts=artifacts,
            )
            staged.append(
                ProjectWaveStageEntry(
                    item_id=action.item_id,
                    display_name=action.display_name,
                    item_type=action.item_type,
                    deployment_wave=action.deployment_wave or plan.current_wave,
                    capability_id=capability.id,
                    plan_id=mutation_plan.plan_id,
                    confirmation_text=mutation_plan.confirmation_text,
                    artifact_sha256=[artifact.sha256 for artifact in mutation_plan.artifacts],
                )
            )
        except (UnsafeOperation, ValueError, RuntimeError) as exc:
            issues.append(
                ProjectWaveStageIssue(
                    item_id=action.item_id,
                    display_name=action.display_name,
                    detail=str(exc),
                )
            )

    if staged and issues:
        status = "partial"
    elif staged:
        status = "staged"
    else:
        status = "blocked"

    return ProjectWaveStageResult(
        template_id=template.id,
        project_name=template.name,
        workspace_id=request.workspace_id,
        wave=plan.current_wave,
        status=status,
        staged=staged,
        issues=issues,
        note=(
            f"Staged {len(staged)} guarded Change Plan(s) for deployment wave {plan.current_wave}. "
            "Nothing has been executed; validate and approve each plan independently in Change Plans."
            if staged
            else f"Deployment wave {plan.current_wave} could not be staged."
        ),
    )
