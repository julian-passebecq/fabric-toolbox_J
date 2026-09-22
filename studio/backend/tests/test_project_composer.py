import base64
import json

import pytest

from app.models import ProjectPlanRequest
from app.project_composer import accept_project, build_eventstream_definition, build_project_item_definition_artifact, get_project_template, list_project_templates, plan_project


def test_foilo_template_covers_rti_and_engineering_items():
    template = get_project_template("foilo-wind-rti")
    item_types = {item.type for item in template.items}

    assert template.workspace_name == "Foilo-Wind-Dev"
    assert {"Eventhouse", "KQLDatabase", "Eventstream", "KQLDashboard"}.issubset(item_types)
    assert {"Lakehouse", "Environment", "Notebook", "DataPipeline"}.issubset(item_types)
    eventstream = next(item for item in template.items if item.type == "Eventstream")
    database = next(item for item in template.items if item.type == "KQLDatabase")
    parameter_names = {parameter.name for parameter in template.parameters}

    assert "rti-kql-database" in eventstream.depends_on
    assert eventstream.vscode_handoff is True
    assert database.settings["parentEventhouseRef"] == "rti-eventhouse"
    assert {"ingestion_mode", "kafka_topic", "kafka_bootstrap_servers", "kafka_password", "turbine_id"}.issubset(parameter_names)


def test_templates_are_discoverable():
    templates = list_project_templates()
    assert any(template.id == "foilo-wind-rti" for template in templates)


def test_new_workspace_plan_marks_all_desired_items_for_create():
    template = get_project_template("foilo-wind-rti")
    plan = plan_project(template, ProjectPlanRequest())

    assert plan.workspace_action == "create"
    assert plan.live_inventory is False
    assert plan.counts["create"] == len(template.items)
    assert plan.counts["conflict"] == 0
    assert plan.apply_supported is False


def test_existing_items_are_unchanged_and_unmanaged_items_are_preserved():
    template = get_project_template("foilo-wind-rti")
    current = [
        {"id": "1", "displayName": "foilo_rti", "type": "Eventhouse"},
        {"id": "2", "displayName": "wind_telemetry", "type": "KQLDatabase"},
        {"id": "3", "displayName": "other_team_item", "type": "Notebook"},
    ]

    plan = plan_project(
        template,
        ProjectPlanRequest(workspace_id="workspace-1", current_items=current),
    )

    by_name = {action.display_name: action for action in plan.actions}
    assert plan.workspace_action == "use-existing"
    assert by_name["foilo_rti"].action == "unchanged"
    assert by_name["wind_telemetry"].action == "unchanged"
    assert by_name["other_team_item"].action == "unmanaged"
    assert plan.counts["unmanaged"] == 1


def test_same_name_with_wrong_type_is_conflict():
    template = get_project_template("foilo-wind-rti")
    plan = plan_project(
        template,
        ProjectPlanRequest(
            workspace_id="workspace-1",
            current_items=[{"displayName": "wind_events", "type": "Notebook"}],
        ),
    )

    action = next(action for action in plan.actions if action.display_name == "wind_events")
    assert action.action == "conflict"
    assert "Notebook" in action.reason


def test_project_parameters_resolve_defaults_and_report_missing():
    template = get_project_template("foilo-wind-rti")
    plan = plan_project(
        template,
        ProjectPlanRequest(parameters={"environment": "", "kafka_topic": "foil.custom.telemetry"}),
    )

    assert "environment" in plan.missing_parameters
    assert plan.resolved_parameters["kafka_topic"] == "foil.custom.telemetry"
    assert plan.resolved_parameters["ingestion_mode"] == "fabric-kafka-endpoint"
    assert "Missing required project parameters" in plan.apply_note


def test_unknown_project_parameter_is_rejected():
    template = get_project_template("foilo-wind-rti")
    with pytest.raises(ValueError, match="Unknown project parameters"):
        plan_project(template, ProjectPlanRequest(parameters={"not_registered": "x"}))


def test_allowed_values_and_secret_redaction():
    template = get_project_template("foilo-wind-rti")

    with pytest.raises(ValueError, match="allowed values"):
        plan_project(
            template,
            ProjectPlanRequest(parameters={"ingestion_mode": "unsupported-mode"}),
        )

    plan = plan_project(
        template,
        ProjectPlanRequest(parameters={"kafka_password": "top-secret"}),
    )
    assert plan.resolved_parameters["kafka_password"] == "***"


def test_project_api_functions_expose_template_and_validate_parameters():
    from fastapi import HTTPException
    from app.main import project_plan as api_project_plan
    from app.main import project_template as api_project_template
    from app.main import project_templates as api_project_templates

    assert any(item.id == "foilo-wind-rti" for item in api_project_templates())
    assert api_project_template("foilo-wind-rti").id == "foilo-wind-rti"

    plan = api_project_plan(
        "foilo-wind-rti",
        ProjectPlanRequest(current_items=[], parameters={"environment": "test"}),
    )
    assert plan.resolved_parameters["environment"] == "test"

    with pytest.raises(HTTPException) as invalid:
        api_project_plan(
            "foilo-wind-rti",
            ProjectPlanRequest(current_items=[], parameters={"environment": "invalid"}),
        )
    assert invalid.value.status_code == 400

    with pytest.raises(HTTPException) as missing:
        api_project_template("does-not-exist")
    assert missing.value.status_code == 404


def test_first_foilo_provisioning_wave_is_dependency_safe():
    template = get_project_template("foilo-wind-rti")
    plan = plan_project(
        template,
        ProjectPlanRequest(workspace_id="workspace-1", current_items=[]),
    )

    by_id = {action.item_id: action for action in plan.actions}

    assert by_id["rti-eventhouse"].provisioning_ready is True
    assert by_id["de-lakehouse"].provisioning_ready is True
    assert by_id["de-environment"].provisioning_ready is True

    assert by_id["rti-kql-database"].provisioning_ready is False
    assert "rti-eventhouse" in by_id["rti-kql-database"].provisioning_reason
    assert by_id["rti-eventstream"].provisioning_ready is False
    assert by_id["de-bronze-notebook"].provisioning_ready is False


def test_kql_database_becomes_ready_when_parent_eventhouse_exists():
    template = get_project_template("foilo-wind-rti")
    current = [
        {"id": "eventhouse-123", "displayName": "foilo_rti", "type": "Eventhouse"},
        {"id": "lakehouse-123", "displayName": "foilo_lakehouse", "type": "Lakehouse"},
        {"id": "environment-123", "displayName": "foilo_spark", "type": "Environment"},
    ]

    plan = plan_project(
        template,
        ProjectPlanRequest(workspace_id="workspace-1", current_items=current),
    )
    by_id = {action.item_id: action for action in plan.actions}
    database = by_id["rti-kql-database"]
    bronze = by_id["de-bronze-notebook"]

    assert database.provisioning_ready is True
    assert database.provisioning_capability_id == "ps-kql-database-new-fabrickqldatabase"
    assert database.provisioning_parameters == {
        "WorkspaceId": "workspace-1",
        "KQLDatabaseName": "wind_telemetry",
        "KQLDatabaseDescription": "KQL database for turbine telemetry, alarms and operational state.",
        "parentEventhouseId": "eventhouse-123",
        "KQLDatabaseType": "ReadWrite",
    }

    assert bronze.provisioning_ready is True
    assert bronze.provisioning_capability_id == "ps-notebook-new-fabricnotebook"
    assert bronze.provisioning_parameters["WorkspaceId"] == "workspace-1"
    assert bronze.provisioning_parameters["NotebookName"] == "bronze_ingestion"


def test_kql_dashboard_waits_for_database_and_queryset_dependencies():
    template = get_project_template("foilo-wind-rti")
    current = [
        {"id": "db-1", "displayName": "wind_telemetry", "type": "KQLDatabase"},
        {"id": "queryset-1", "displayName": "wind_operations", "type": "KQLQueryset"},
    ]

    plan = plan_project(
        template,
        ProjectPlanRequest(workspace_id="workspace-1", current_items=current),
    )
    dashboard = next(action for action in plan.actions if action.item_id == "rti-dashboard")

    assert dashboard.provisioning_ready is True
    assert dashboard.provisioning_capability_id == "ps-kql-dashboard-new-fabrickqldashboard"
    assert dashboard.provisioning_parameters["KQLDashboardName"] == "wind_realtime_dashboard"


def test_eventstream_artifact_uses_custom_endpoint_and_eventhouse_destination():
    from app.project_composer import build_eventstream_definition

    template = get_project_template("foilo-wind-rti")
    artifact = build_eventstream_definition(
        template,
        ProjectPlanRequest(
            workspace_id="workspace-1",
            current_items=[
                {"id": "eventhouse-123", "displayName": "foilo_rti", "type": "Eventhouse"},
                {"id": "database-123", "displayName": "wind_telemetry", "type": "KQLDatabase"},
            ],
        ),
    )

    assert artifact["ready"] is True
    assert artifact["source_mode"] == "fabric-kafka-endpoint"
    definition = artifact["definition"]
    assert definition["sources"][0]["type"] == "CustomEndpoint"
    assert definition["streams"][0]["inputNodes"] == [{"name": "foilo-kafka-ingress"}]
    destination = definition["destinations"][0]
    assert destination["type"] == "Eventhouse"
    assert destination["properties"]["itemId"] == "eventhouse-123"
    assert destination["properties"]["databaseName"] == "wind_telemetry"
    assert destination["properties"]["tableName"] == "turbine_telemetry"
    assert definition["compatibilityLevel"] == "1.1"


def test_direct_kafka_eventstream_artifact_requires_fabric_connection_id():
    from app.project_composer import build_eventstream_definition

    template = get_project_template("foilo-wind-rti")
    request = ProjectPlanRequest(
        workspace_id="workspace-1",
        current_items=[
            {"id": "eventhouse-123", "displayName": "foilo_rti", "type": "Eventhouse"},
            {"id": "database-123", "displayName": "wind_telemetry", "type": "KQLDatabase"},
        ],
        parameters={"ingestion_mode": "direct-kafka-source"},
    )
    artifact = build_eventstream_definition(template, request)
    assert artifact["ready"] is False
    assert "kafka_connection_id" in artifact["missing_requirements"]

    request.parameters["kafka_connection_id"] = "connection-123"
    request.parameters["kafka_topic"] = "foil.wind.telemetry"
    artifact = build_eventstream_definition(template, request)
    source = artifact["definition"]["sources"][0]

    assert artifact["ready"] is True
    assert source["type"] == "ApacheKafka"
    assert source["properties"]["dataConnectionId"] == "connection-123"
    assert source["properties"]["topic"] == "foil.wind.telemetry"
    assert source["properties"]["consumerGroupName"] == "foilo-fabric-consumer"


def test_eventstream_artifact_api_exposes_definition_without_logging_secrets():
    from app.main import project_eventstream_artifact

    response = project_eventstream_artifact(
        "foilo-wind-rti",
        ProjectPlanRequest(
            workspace_id="workspace-1",
            current_items=[
                {"id": "eventhouse-123", "displayName": "foilo_rti", "type": "Eventhouse"},
                {"id": "database-123", "displayName": "wind_telemetry", "type": "KQLDatabase"},
            ],
            parameters={"kafka_password": "do-not-return", "kql_table_name": "telemetry_raw"},
        ),
    )

    assert response["filename"] == "eventstream.json"
    assert response["definition"]["destinations"][0]["properties"]["tableName"] == "telemetry_raw"
    assert "do-not-return" not in str(response)


def test_existing_eventstream_exposes_guarded_definition_reconciliation():
    template = get_project_template("foilo-wind-rti")
    current = [
        {"id": "eventhouse-1", "displayName": "foilo_rti", "type": "Eventhouse"},
        {"id": "database-1", "displayName": "wind_telemetry", "type": "KQLDatabase"},
        {"id": "eventstream-1", "displayName": "wind_events", "type": "Eventstream"},
    ]

    plan = plan_project(
        template,
        ProjectPlanRequest(workspace_id="workspace-1", current_items=current),
    )
    eventstream = next(action for action in plan.actions if action.item_id == "rti-eventstream")

    assert eventstream.action == "unchanged"
    assert eventstream.provisioning_ready is False
    assert eventstream.reconciliation_ready is True
    assert eventstream.reconciliation_capability_id == "ps-eventstream-update-fabriceventstreamdefinition"
    assert eventstream.reconciliation_parameters == {
        "WorkspaceId": "workspace-1",
        "EventstreamId": "eventstream-1",
    }
    assert "guarded" in eventstream.reconciliation_reason.lower()


def test_missing_eventstream_does_not_offer_definition_reconciliation():
    template = get_project_template("foilo-wind-rti")
    plan = plan_project(
        template,
        ProjectPlanRequest(
            workspace_id="workspace-1",
            current_items=[
                {"id": "eventhouse-1", "displayName": "foilo_rti", "type": "Eventhouse"},
                {"id": "database-1", "displayName": "wind_telemetry", "type": "KQLDatabase"},
            ],
        ),
    )
    eventstream = next(action for action in plan.actions if action.item_id == "rti-eventstream")

    assert eventstream.action == "create"
    assert eventstream.reconciliation_ready is False
    assert eventstream.reconciliation_capability_id is None


def test_existing_eventstream_reconciliation_waits_for_declared_dependencies():
    template = get_project_template("foilo-wind-rti")
    plan = plan_project(
        template,
        ProjectPlanRequest(
            workspace_id="workspace-1",
            current_items=[
                {"id": "eventstream-1", "displayName": "wind_events", "type": "Eventstream"},
            ],
        ),
    )
    eventstream = next(action for action in plan.actions if action.item_id == "rti-eventstream")

    assert eventstream.action == "unchanged"
    assert eventstream.reconciliation_ready is False
    assert eventstream.reconciliation_capability_id == "ps-eventstream-update-fabriceventstreamdefinition"
    assert "rti-eventhouse" in eventstream.reconciliation_reason
    assert "rti-kql-database" in eventstream.reconciliation_reason


def _encoded_eventstream_response(definition):
    payload = base64.b64encode(
        json.dumps(definition, sort_keys=True).encode("utf-8")
    ).decode("ascii")
    return {
        "definition": {
            "parts": [
                {
                    "path": "eventstream.json",
                    "payload": payload,
                    "payloadType": "InlineBase64",
                }
            ]
        }
    }


def _foilo_acceptance_items():
    return [
        {"id": "eventhouse-1", "displayName": "foilo_rti", "type": "Eventhouse"},
        {"id": "database-1", "displayName": "wind_telemetry", "type": "KQLDatabase"},
        {"id": "eventstream-1", "displayName": "wind_events", "type": "Eventstream"},
        {"id": "lakehouse-1", "displayName": "foilo_lakehouse", "type": "Lakehouse"},
    ]


def test_foilo_deployment_acceptance_passes_when_live_topology_matches(monkeypatch):
    template = get_project_template("foilo-wind-rti")
    request = ProjectPlanRequest(
        workspace_id="workspace-1",
        current_items=_foilo_acceptance_items(),
    )
    desired = build_eventstream_definition(template, request)["definition"]

    monkeypatch.setattr(
        "app.project_composer.runtime.execute_read",
        lambda capability, parameters: _encoded_eventstream_response(desired),
    )

    report = accept_project(template, request)

    assert report.accepted is True
    assert report.status == "pass"
    assert report.definition_match is True
    assert report.desired_eventstream_sha256 == report.live_eventstream_sha256
    assert all(check.status == "pass" for check in report.checks)
    topology = next(check for check in report.checks if check.id == "eventstream-definition")
    assert topology.item_id == "eventstream-1"


def test_foilo_deployment_acceptance_detects_eventstream_drift(monkeypatch):
    template = get_project_template("foilo-wind-rti")
    request = ProjectPlanRequest(
        workspace_id="workspace-1",
        current_items=_foilo_acceptance_items(),
    )
    live = build_eventstream_definition(template, request)["definition"]
    live["destinations"][0]["properties"]["tableName"] = "wrong_table"

    monkeypatch.setattr(
        "app.project_composer.runtime.execute_read",
        lambda capability, parameters: _encoded_eventstream_response(live),
    )

    report = accept_project(template, request)

    assert report.accepted is False
    assert report.status == "fail"
    assert report.definition_match is False
    assert report.desired_eventstream_sha256 != report.live_eventstream_sha256
    topology = next(check for check in report.checks if check.id == "eventstream-definition")
    assert topology.status == "fail"
    assert "reconciliation" in topology.detail.lower()


def test_foilo_deployment_acceptance_reports_missing_core_item(monkeypatch):
    template = get_project_template("foilo-wind-rti")
    items = [item for item in _foilo_acceptance_items() if item["type"] != "Lakehouse"]
    request = ProjectPlanRequest(workspace_id="workspace-1", current_items=items)
    desired = build_eventstream_definition(template, request)["definition"]

    monkeypatch.setattr(
        "app.project_composer.runtime.execute_read",
        lambda capability, parameters: _encoded_eventstream_response(desired),
    )

    report = accept_project(template, request)

    assert report.accepted is False
    lakehouse = next(check for check in report.checks if check.id == "item:de-lakehouse")
    assert lakehouse.status == "fail"
    assert "missing" in lakehouse.detail.lower()


def test_foilo_deployment_acceptance_requires_workspace_id():
    template = get_project_template("foilo-wind-rti")
    with pytest.raises(ValueError, match="workspace_id"):
        accept_project(template, ProjectPlanRequest(current_items=[]))


def test_project_acceptance_api_returns_hashes_without_live_definition(monkeypatch):
    from app.main import project_acceptance

    template = get_project_template("foilo-wind-rti")
    request = ProjectPlanRequest(
        workspace_id="workspace-1",
        current_items=_foilo_acceptance_items(),
    )
    desired = build_eventstream_definition(template, request)["definition"]
    monkeypatch.setattr(
        "app.project_composer.runtime.execute_read",
        lambda capability, parameters: _encoded_eventstream_response(desired),
    )

    response = project_acceptance("foilo-wind-rti", request)

    assert response.accepted is True
    assert response.desired_eventstream_sha256
    assert response.live_eventstream_sha256
    serialized = response.model_dump()
    assert "definition" not in serialized


def _foilo_engineering_items():
    return [
        {"id": "lakehouse-1", "displayName": "foilo_lakehouse", "type": "Lakehouse"},
        {"id": "environment-1", "displayName": "foilo_spark", "type": "Environment"},
        {"id": "bronze-1", "displayName": "bronze_ingestion", "type": "Notebook"},
        {"id": "silver-1", "displayName": "silver_transform", "type": "Notebook"},
        {"id": "pipeline-1", "displayName": "wind_ingestion_pipeline", "type": "DataPipeline"},
    ]


def test_bronze_notebook_artifact_binds_live_lakehouse_environment_and_turbine():
    template = get_project_template("foilo-wind-rti")
    artifact = build_project_item_definition_artifact(
        template,
        "de-bronze-notebook",
        ProjectPlanRequest(
            workspace_id="workspace-1",
            current_items=_foilo_engineering_items(),
            parameters={"turbine_id": "FOILO-WT-042"},
        ),
    )

    assert artifact["ready"] is True
    assert artifact["item_type"] == "Notebook"
    assert artifact["filename"] == "notebook-content.py"
    assert artifact["artifact_parameter"] == "NotebookPathDefinition"
    assert artifact["mutation_parameters"] == {"NotebookFormat": "fabricGitSource"}
    assert artifact["content_sha256"]
    assert "lakehouse-1" in artifact["content"]
    assert "environment-1" in artifact["content"]
    assert "workspace-1" in artifact["content"]
    assert "FOILO-WT-042" in artifact["content"]
    assert "bronze_turbine_telemetry" in artifact["content"]


def test_silver_notebook_artifact_contains_quality_transform():
    template = get_project_template("foilo-wind-rti")
    artifact = build_project_item_definition_artifact(
        template,
        "de-silver-notebook",
        ProjectPlanRequest(
            workspace_id="workspace-1",
            current_items=_foilo_engineering_items(),
        ),
    )

    assert artifact["ready"] is True
    assert "silver_turbine_telemetry" in artifact["content"]
    assert 'dropDuplicates(["turbine_id", "event_time"])' in artifact["content"]
    assert "wind_speed_ms" in artifact["content"]


def test_pipeline_artifact_orchestrates_live_notebook_ids_in_order():
    template = get_project_template("foilo-wind-rti")
    artifact = build_project_item_definition_artifact(
        template,
        "df-pipeline",
        ProjectPlanRequest(
            workspace_id="workspace-1",
            current_items=_foilo_engineering_items(),
        ),
    )

    assert artifact["ready"] is True
    assert artifact["item_type"] == "DataPipeline"
    assert artifact["filename"] == "pipeline-content.json"
    assert artifact["artifact_parameter"] is None

    content = json.loads(artifact["content"])
    activities = content["properties"]["activities"]
    assert [activity["type"] for activity in activities] == ["TridentNotebook", "TridentNotebook"]
    assert activities[0]["typeProperties"] == {
        "notebookId": "bronze-1",
        "workspaceId": "workspace-1",
    }
    assert activities[1]["typeProperties"] == {
        "notebookId": "silver-1",
        "workspaceId": "workspace-1",
    }
    assert activities[1]["dependsOn"] == [
        {"activity": "bronze_ingestion", "dependencyConditions": ["Succeeded"]}
    ]

    definition = artifact["mutation_parameters"]["Definition"]
    part = definition["parts"][0]
    assert part["path"] == "pipeline-content.json"
    assert part["payloadType"] == "InlineBase64"
    decoded = base64.b64decode(part["payload"]).decode("utf-8")
    assert json.loads(decoded) == content


def test_notebook_and_pipeline_existing_items_expose_definition_reconciliation():
    template = get_project_template("foilo-wind-rti")
    plan = plan_project(
        template,
        ProjectPlanRequest(
            workspace_id="workspace-1",
            current_items=_foilo_engineering_items(),
        ),
    )
    by_id = {action.item_id: action for action in plan.actions}

    bronze = by_id["de-bronze-notebook"]
    silver = by_id["de-silver-notebook"]
    pipeline = by_id["df-pipeline"]

    assert bronze.reconciliation_ready is True
    assert bronze.reconciliation_capability_id == "ps-notebook-update-fabricnotebookdefinition"
    assert bronze.reconciliation_parameters == {
        "WorkspaceId": "workspace-1",
        "NotebookId": "bronze-1",
        "NotebookFormat": "fabricGitSource",
    }

    assert silver.reconciliation_ready is True
    assert silver.reconciliation_capability_id == "ps-notebook-update-fabricnotebookdefinition"

    assert pipeline.reconciliation_ready is True
    assert pipeline.reconciliation_capability_id == "ps-data-pipeline-update-fabricdatapipelinedefinition"
    assert pipeline.reconciliation_parameters == {
        "WorkspaceId": "workspace-1",
        "DataPipelineId": "pipeline-1",
    }


def test_notebook_create_plan_declares_fabric_git_source_format():
    template = get_project_template("foilo-wind-rti")
    plan = plan_project(
        template,
        ProjectPlanRequest(
            workspace_id="workspace-1",
            current_items=[
                {"id": "lakehouse-1", "displayName": "foilo_lakehouse", "type": "Lakehouse"},
                {"id": "environment-1", "displayName": "foilo_spark", "type": "Environment"},
            ],
        ),
    )
    bronze = next(action for action in plan.actions if action.item_id == "de-bronze-notebook")

    assert bronze.provisioning_ready is True
    assert bronze.provisioning_parameters["NotebookFormat"] == "fabricGitSource"


def test_project_item_artifact_api_returns_definition_without_mutating():
    from app.main import project_item_definition_artifact

    response = project_item_definition_artifact(
        "foilo-wind-rti",
        "df-pipeline",
        ProjectPlanRequest(
            workspace_id="workspace-1",
            current_items=_foilo_engineering_items(),
        ),
    )

    assert response["ready"] is True
    assert response["content_sha256"]
    assert response["mutation_parameters"]["Definition"]["parts"][0]["path"] == "pipeline-content.json"
