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
    ProjectManifest,
    ProjectManifestExportRequest,
    ProjectManifestImportResult,
    ProjectPlan,
    ProjectPlanAction,
    ProjectPlanRequest,
    ProjectTemplate,
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



def _template_sha256(template: ProjectTemplate) -> str:
    payload = json.dumps(
        template.model_dump(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def export_project_manifest(
    template: ProjectTemplate,
    request: ProjectManifestExportRequest,
) -> ProjectManifest:
    _, missing_parameters = _resolve_parameters(template, request.parameters)
    specs = {parameter.name: parameter for parameter in template.parameters}

    safe_parameters: dict[str, Any] = {}
    secret_parameters: list[str] = []
    for name, spec in specs.items():
        value = request.parameters.get(name, spec.default)
        if spec.secret:
            safe_parameters[name] = None
            secret_parameters.append(name)
        else:
            safe_parameters[name] = value

    return ProjectManifest(
        template_id=template.id,
        template_version=template.version,
        template_sha256=_template_sha256(template),
        project_name=template.name,
        workspace_id=request.workspace_id,
        workspace_name=request.workspace_name or template.workspace_name,
        parameters=safe_parameters,
        secret_parameters=sorted(secret_parameters),
        missing_parameters=missing_parameters,
        items=template.items,
    )


def import_project_manifest(manifest: ProjectManifest) -> ProjectManifestImportResult:
    template = get_project_template(manifest.template_id)
    warnings: list[str] = []

    current_sha = _template_sha256(template)
    if manifest.template_version != template.version:
        warnings.append(
            f"Template version differs: manifest={manifest.template_version}, current={template.version}."
        )
    if manifest.template_sha256 != current_sha:
        warnings.append("Template content differs from the current registered template.")

    current_items = {(item.id, item.type, item.display_name) for item in template.items}
    imported_items = {(item.id, item.type, item.display_name) for item in manifest.items}
    if current_items != imported_items:
        warnings.append("Manifest desired item graph differs from the current template.")

    specs = {parameter.name: parameter for parameter in template.parameters}
    unknown = sorted(set(manifest.parameters) - set(specs))
    if unknown:
        raise ValueError("Unknown manifest parameters: " + ", ".join(unknown))

    parameters: dict[str, Any] = {}
    secret_parameters: list[str] = []
    missing_parameters: list[str] = []

    for name, spec in specs.items():
        imported_value = manifest.parameters.get(name, spec.default)
        if spec.secret:
            secret_parameters.append(name)
            if imported_value not in (None, "", "***", "***REDACTED***"):
                warnings.append(f"Secret parameter '{name}' was ignored during import.")
            parameters[name] = spec.default if spec.default is not None else ""
            continue

        if spec.allowed_values and imported_value not in (None, "") and str(imported_value) not in spec.allowed_values:
            allowed = ", ".join(spec.allowed_values)
            raise ValueError(f"Invalid value for {name}; allowed values: {allowed}")

        parameters[name] = imported_value
        if spec.required and imported_value in (None, ""):
            missing_parameters.append(name)

    if missing_parameters:
        warnings.append(
            "Imported manifest is incomplete; required parameters still missing: "
            + ", ".join(missing_parameters)
            + "."
        )

    return ProjectManifestImportResult(
        template_id=template.id,
        imported_template_version=manifest.template_version,
        current_template_version=template.version,
        workspace_id=manifest.workspace_id,
        workspace_name=manifest.workspace_name or template.workspace_name,
        parameters=parameters,
        secret_parameters=sorted(secret_parameters),
        warnings=warnings,
    )

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

    if desired.type == "Notebook":
        parameters["NotebookFormat"] = "fabricGitSource"

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



RECONCILERS: dict[str, dict[str, str]] = {
    "Eventstream": {
        "capability_id": "ps-eventstream-update-fabriceventstreamdefinition",
        "id_parameter": "EventstreamId",
    },
    "Notebook": {
        "capability_id": "ps-notebook-update-fabricnotebookdefinition",
        "id_parameter": "NotebookId",
    },
    "DataPipeline": {
        "capability_id": "ps-data-pipeline-update-fabricdatapipelinedefinition",
        "id_parameter": "DataPipelineId",
    },
}


def _reconciliation_for(
    desired,
    action: str,
    request: ProjectPlanRequest,
    existing_item: dict[str, Any] | None,
    existing_by_template_id: dict[str, dict[str, Any]],
    catalog_by_id: dict[str, Any],
) -> tuple[str | None, dict[str, Any], bool, str]:
    reconciler = RECONCILERS.get(desired.type)
    if not reconciler:
        return None, {}, False, ""

    capability_id = reconciler["capability_id"]
    item_label = desired.type

    if action != "unchanged" or not existing_item:
        return (
            None,
            {},
            False,
            f"Definition reconciliation becomes available after the {item_label} exists in Fabric.",
        )

    capability = catalog_by_id.get(capability_id)
    if not capability or capability.execution_policy != "guarded-write":
        return capability_id, {}, False, f"The reviewed {item_label} definition update capability is not enabled."

    if not request.workspace_id:
        return capability_id, {}, False, f"Select the live workspace before reconciling a {item_label} definition."

    item_id = _actual_id(existing_item)
    if not item_id:
        return capability_id, {}, False, f"The existing {item_label} item ID could not be resolved."

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

    parameters: dict[str, Any] = {
        "WorkspaceId": request.workspace_id,
        reconciler["id_parameter"]: item_id,
    }
    if desired.type == "Notebook":
        parameters["NotebookFormat"] = "fabricGitSource"

    return (
        capability_id,
        parameters,
        True,
        f"Existing {item_label} can be reconciled to the generated project definition through a guarded Change Plan.",
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


def _project_actual_by_template_id(
    template: ProjectTemplate,
    request: ProjectPlanRequest,
) -> tuple[dict[str, dict[str, Any]], bool]:
    current_items = request.current_items
    live_inventory = False
    if current_items is None:
        if request.workspace_id:
            current_items = _live_items(request.workspace_id)
            live_inventory = True
        else:
            current_items = []

    by_name_type: dict[tuple[str, str], dict[str, Any]] = {}
    for item in current_items:
        if not isinstance(item, dict):
            continue
        name = _actual_name(item).strip()
        item_type = _actual_type(item).strip()
        if name:
            by_name_type[(name.casefold(), item_type.casefold())] = item

    actual_by_template_id: dict[str, dict[str, Any]] = {}
    for desired in template.items:
        actual = by_name_type.get((desired.display_name.casefold(), desired.type.casefold()))
        if actual:
            actual_by_template_id[desired.id] = actual
    return actual_by_template_id, live_inventory


def _fabric_notebook_metadata_lines(metadata: dict[str, Any]) -> str:
    body = json.dumps(metadata, indent=2)
    return "\n".join("# META " + line for line in body.splitlines())


def _fabric_notebook_cell_metadata() -> str:
    return _fabric_notebook_metadata_lines(
        {"language": "python", "language_group": "synapse_pyspark"}
    )


def _foilo_notebook_source(
    desired,
    workspace_id: str,
    lakehouse_id: str,
    lakehouse_name: str,
    environment_id: str,
    turbine_id: str,
) -> str:
    metadata = {
        "kernel_info": {"name": "synapse_pyspark"},
        "dependencies": {
            "lakehouse": {
                "default_lakehouse": lakehouse_id,
                "default_lakehouse_name": lakehouse_name,
                "default_lakehouse_workspace_id": workspace_id,
                "known_lakehouses": [{"id": lakehouse_id}],
            },
            "environment": {
                "environmentId": environment_id,
                "workspaceId": workspace_id,
            },
        },
    }

    if desired.id == "de-bronze-notebook":
        code = f'''from pyspark.sql import functions as F, types as T

TURBINE_ID = {json.dumps(turbine_id)}
SOURCE_PATH = "Files/foilo/incoming/*.json"
BRONZE_TABLE = "bronze_turbine_telemetry"

schema = T.StructType([
    T.StructField("timestamp", T.StringType()),
    T.StructField("turbine_id", T.StringType()),
    T.StructField("wind_speed_ms", T.DoubleType()),
    T.StructField("wind_direction_deg", T.DoubleType()),
    T.StructField("rotor_rpm", T.DoubleType()),
    T.StructField("generator_rpm", T.DoubleType()),
    T.StructField("blade_pitch_deg", T.DoubleType()),
    T.StructField("yaw_angle_deg", T.DoubleType()),
    T.StructField("power_kw", T.DoubleType()),
    T.StructField("power_target_kw", T.DoubleType()),
    T.StructField("gearbox_temp_c", T.DoubleType()),
    T.StructField("generator_temp_c", T.DoubleType()),
    T.StructField("bearing_temp_c", T.DoubleType()),
    T.StructField("vibration_mm_s", T.DoubleType()),
    T.StructField("status", T.StringType()),
    T.StructField("alarm_code", T.StringType()),
])

raw = spark.read.schema(schema).json(SOURCE_PATH)
bronze = (
    raw
    .withColumn("turbine_id", F.coalesce(F.col("turbine_id"), F.lit(TURBINE_ID)))
    .withColumn("ingested_at", F.current_timestamp())
    .withColumn("source_file", F.input_file_name())
)

bronze.write.format("delta").mode("append").saveAsTable(BRONZE_TABLE)
print(f"Wrote {{bronze.count()}} rows to {{BRONZE_TABLE}}")
'''
        title = "# Foil'o Bronze telemetry ingestion"
    elif desired.id == "de-silver-notebook":
        code = '''from pyspark.sql import functions as F

BRONZE_TABLE = "bronze_turbine_telemetry"
SILVER_TABLE = "silver_turbine_telemetry"

bronze = spark.table(BRONZE_TABLE)
silver = (
    bronze
    .withColumn("event_time", F.to_timestamp("timestamp"))
    .filter(F.col("event_time").isNotNull())
    .filter(F.col("turbine_id").isNotNull())
    .filter((F.col("wind_speed_ms") >= 0) & (F.col("wind_speed_ms") <= 80))
    .filter((F.col("vibration_mm_s").isNull()) | (F.col("vibration_mm_s") >= 0))
    .dropDuplicates(["turbine_id", "event_time"])
    .select(
        "event_time",
        "turbine_id",
        "wind_speed_ms",
        "wind_direction_deg",
        "rotor_rpm",
        "generator_rpm",
        "blade_pitch_deg",
        "yaw_angle_deg",
        "power_kw",
        "power_target_kw",
        "gearbox_temp_c",
        "generator_temp_c",
        "bearing_temp_c",
        "vibration_mm_s",
        "status",
        "alarm_code",
        "ingested_at",
        "source_file",
    )
)

silver.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(SILVER_TABLE)
print(f"Wrote {silver.count()} rows to {SILVER_TABLE}")
'''
        title = "# Foil'o Silver telemetry quality + normalization"
    else:
        raise ValueError(f"No generated Notebook source is registered for {desired.id}")

    return "\n".join(
        [
            "# Fabric notebook source",
            "",
            "# METADATA ********************",
            _fabric_notebook_metadata_lines(metadata),
            "",
            "# MARKDOWN ********************",
            title,
            "",
            "# CELL ********************",
            code.rstrip(),
            "",
            "# METADATA ********************",
            _fabric_notebook_cell_metadata(),
            "",
        ]
    )


def build_project_item_definition_artifact(
    template: ProjectTemplate,
    item_id: str,
    request: ProjectPlanRequest,
) -> dict[str, Any]:
    resolved_parameters, missing_parameters = _resolve_parameters(template, request.parameters)
    desired = next((item for item in template.items if item.id == item_id), None)
    if not desired:
        raise ValueError(f"Project item not found: {item_id}")
    if desired.type not in {"Notebook", "DataPipeline"}:
        raise ValueError(f"Generated definition artifact is not registered for {desired.type}")

    actual_by_template_id, live_inventory = _project_actual_by_template_id(template, request)
    missing_requirements = list(missing_parameters)
    if not request.workspace_id:
        missing_requirements.append("workspace_id")

    content = ""
    mutation_parameters: dict[str, Any] = {}
    artifact_parameter: str | None = None
    filename = ""

    if desired.type == "Notebook":
        lakehouse_ref = next(
            (
                dependency for dependency in desired.depends_on
                if next((item for item in template.items if item.id == dependency and item.type == "Lakehouse"), None)
            ),
            "",
        )
        environment_ref = next(
            (
                dependency for dependency in desired.depends_on
                if next((item for item in template.items if item.id == dependency and item.type == "Environment"), None)
            ),
            "",
        )
        lakehouse = actual_by_template_id.get(lakehouse_ref)
        environment = actual_by_template_id.get(environment_ref)
        lakehouse_id = _actual_id(lakehouse)
        environment_id = _actual_id(environment)
        if not lakehouse_id:
            missing_requirements.append("lakehouse_item_id")
        if not environment_id:
            missing_requirements.append("environment_item_id")

        if request.workspace_id and lakehouse_id and environment_id:
            lakehouse_item = next(item for item in template.items if item.id == lakehouse_ref)
            content = _foilo_notebook_source(
                desired,
                request.workspace_id,
                lakehouse_id,
                lakehouse_item.display_name,
                environment_id,
                str(resolved_parameters.get("turbine_id") or "FOILO-WT-001"),
            )
        filename = "notebook-content.py"
        artifact_parameter = "NotebookPathDefinition"
        mutation_parameters = {"NotebookFormat": "fabricGitSource"}

    elif desired.type == "DataPipeline":
        notebook_refs = [
            dependency for dependency in desired.depends_on
            if next((item for item in template.items if item.id == dependency and item.type == "Notebook"), None)
        ]
        notebook_items: list[tuple[Any, str]] = []
        for ref in notebook_refs:
            actual = actual_by_template_id.get(ref)
            actual_id = _actual_id(actual)
            if not actual_id:
                missing_requirements.append(f"{ref}_item_id")
            else:
                notebook_items.append((next(item for item in template.items if item.id == ref), actual_id))

        if request.workspace_id and len(notebook_items) == len(notebook_refs) and notebook_items:
            activities: list[dict[str, Any]] = []
            previous_name: str | None = None
            for desired_notebook, notebook_id in notebook_items:
                activity_name = desired_notebook.display_name
                activity: dict[str, Any] = {
                    "name": activity_name,
                    "type": "TridentNotebook",
                    "dependsOn": (
                        [{"activity": previous_name, "dependencyConditions": ["Succeeded"]}]
                        if previous_name else []
                    ),
                    "policy": {
                        "timeout": "0.12:00:00",
                        "retry": 0,
                        "retryIntervalInSeconds": 30,
                    },
                    "typeProperties": {
                        "notebookId": notebook_id,
                        "workspaceId": request.workspace_id,
                    },
                }
                activities.append(activity)
                previous_name = activity_name

            pipeline_content = {
                "properties": {
                    "description": desired.description,
                    "activities": activities,
                }
            }
            content = json.dumps(pipeline_content, indent=2)
            payload = base64.b64encode(content.encode("utf-8")).decode("ascii")
            mutation_parameters = {
                "Definition": {
                    "parts": [
                        {
                            "path": "pipeline-content.json",
                            "payload": payload,
                            "payloadType": "InlineBase64",
                        }
                    ]
                }
            }
        filename = "pipeline-content.json"

    return {
        "template_id": template.id,
        "item_id": desired.id,
        "item_type": desired.type,
        "display_name": desired.display_name,
        "filename": filename,
        "ready": not missing_requirements and bool(content),
        "missing_requirements": sorted(set(missing_requirements)),
        "live_inventory": live_inventory,
        "content": content,
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest() if content else None,
        "artifact_parameter": artifact_parameter,
        "mutation_parameters": mutation_parameters,
        "provenance": {
            "schema": (
                "Microsoft Fabric Notebook definition (fabricGitSource)"
                if desired.type == "Notebook"
                else "Microsoft Fabric DataPipeline definition"
            ),
            "source": "Microsoft Fabric public item definition",
        },
    }
