import pytest

from app.models import ProjectPlanRequest
from app.project_composer import get_project_template, list_project_templates, plan_project


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
