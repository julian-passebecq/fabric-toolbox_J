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
    assert {"ingestion_mode", "kafka_topic", "kafka_bootstrap_servers", "turbine_id"}.issubset(parameter_names)


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
