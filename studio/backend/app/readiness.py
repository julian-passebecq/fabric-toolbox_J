"""Conservative project readiness and bootstrap planning.

M03 deliberately separates local configuration from runtime evidence. This module
does not call Fabric and never grants deployment authorization. It only combines
an already-validated project contract with the backend's current session state and
returns explicit unknowns plus non-executing next steps.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    BootstrapAction,
    ProjectReadinessCheck,
    ProjectReadinessReport,
    SessionStatus,
)
from .project_contract import ProjectContractError, validate_project


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check(
    check_id: str,
    category: str,
    title: str,
    status: str,
    *,
    required: bool,
    evidence_kind: str,
    source: str,
    detail: str,
    next_action: str | None = None,
) -> ProjectReadinessCheck:
    return ProjectReadinessCheck(
        id=check_id,
        category=category,
        title=title,
        status=status,
        required=required,
        evidence_kind=evidence_kind,
        source=source,
        detail=detail,
        next_action=next_action,
    )


def evaluate_project_readiness(
    manifest: dict[str, Any],
    profile_name: str,
    session: SessionStatus,
) -> ProjectReadinessReport:
    """Evaluate project readiness without performing network or provider calls."""
    validation = validate_project(manifest, profile_name=profile_name)
    if not validation.valid:
        first = validation.findings[0]
        raise ProjectContractError(first.code, first.path, first.message)

    project = validation.project
    assert project is not None
    profile = project["profiles"][profile_name]
    evaluated_at = _now()
    checks: list[ProjectReadinessCheck] = []
    actions: list[BootstrapAction] = []

    checks.append(_check(
        "project.contract",
        "Project",
        "Project contract",
        "satisfied",
        required=True,
        evidence_kind="local-contract",
        source="M01 offline project validator",
        detail="Schema and semantic validation passed. This proves only that the local design contract is internally valid.",
    ))

    if session.connected:
        checks.append(_check(
            "identity.fabric-session",
            "Identity",
            "Fabric authentication session",
            "satisfied",
            required=True,
            evidence_kind="backend-session",
            source="Fabric Ops Studio backend session",
            detail=f"Connected backend session for tenant {session.tenant_id or 'unknown'}. This does not prove permissions for every project resource.",
        ))
    else:
        checks.append(_check(
            "identity.fabric-session",
            "Identity",
            "Fabric authentication session",
            "action_required",
            required=True,
            evidence_kind="none",
            source="Fabric Ops Studio backend session",
            detail="No connected Fabric session is available.",
            next_action="Connect to the intended Fabric tenant before runtime discovery.",
        ))
        actions.append(BootstrapAction(
            id="connect-fabric",
            category="Identity",
            title="Connect Fabric session",
            kind="user-action",
            executable=False,
            reason="Interactive authentication must be initiated explicitly by the operator.",
        ))

    checks.append(_check(
        "identity.project-reference",
        "Identity",
        "Project identity reference",
        "satisfied",
        required=True,
        evidence_kind="local-contract",
        source=f"profile:{profile_name}",
        detail=f"Identity reference {profile['identityRef']} is declared. Resolution and permission scope are not yet runtime-evidenced.",
        next_action="Resolve the identity reference during a later provider-read milestone.",
    ))

    checks.append(_check(
        "capacity.project-reference",
        "Capacity",
        "Capacity reference",
        "satisfied",
        required=True,
        evidence_kind="local-contract",
        source=f"profile:{profile_name}",
        detail=f"Capacity reference {profile['capacityRef']} is declared. Capacity existence, state and assignment are not yet runtime-evidenced.",
        next_action="Observe the referenced capacity before any bootstrap mutation is proposed.",
    ))
    actions.append(BootstrapAction(
        id="observe-capacity",
        category="Capacity",
        title="Observe referenced capacity",
        kind="read",
        executable=False,
        reason="M03 records the required read but does not infer a capacity from the local reference.",
    ))

    checks.append(_check(
        "workspace.target",
        "Workspace",
        "Target workspace",
        "unknown",
        required=True,
        evidence_kind="none",
        source=f"profile:{profile_name}",
        detail=f"Desired workspace name is {profile['workspaceDisplayName']}. No provider observation is attached to this project readiness report.",
        next_action="Observe the exact target workspace before deciding whether creation is required.",
    ))
    actions.append(BootstrapAction(
        id="observe-workspace",
        category="Workspace",
        title="Observe target workspace",
        kind="read",
        executable=False,
        reason="Unknown is not treated as missing. A create plan must not be offered until an explicit read proves absence.",
    ))

    for resource_type in sorted({resource["type"] for resource in project["resources"]}):
        checks.append(_check(
            f"support.{resource_type.casefold()}",
            "Fabric support",
            f"{resource_type} support",
            "unknown",
            required=True,
            evidence_kind="none",
            source="No provider observation",
            detail=f"The manifest uses {resource_type}, but M03 has no tenant/capacity support evidence for that resource type.",
            next_action=f"Discover {resource_type} support in the selected tenant/capacity context.",
        ))
    actions.append(BootstrapAction(
        id="observe-resource-support",
        category="Fabric support",
        title="Discover required resource support",
        kind="read",
        executable=False,
        reason="Resource-type support must come from provider evidence rather than the project manifest.",
    ))

    checks.append(_check(
        "deployment.owner",
        "Deployment",
        "Deployment ownership",
        "satisfied",
        required=True,
        evidence_kind="local-contract",
        source=f"profile:{profile_name}",
        detail=f"Deployment owner is explicitly declared as {profile['deploymentOwner']}. This prevents Studio and native Git from silently competing for the same deployment.",
    ))

    if telemetry := project.get("telemetry"):
        checks.append(_check(
            "telemetry.connection-reference",
            "Connections",
            "Telemetry connection reference",
            "satisfied",
            required=True,
            evidence_kind="local-contract",
            source="project.telemetry",
            detail=f"Secret reference {telemetry['sourceConnectionRef']} is declared; no secret value is present in the project contract.",
        ))
        checks.append(_check(
            "telemetry.connection-availability",
            "Connections",
            "Telemetry connection availability",
            "unknown",
            required=True,
            evidence_kind="none",
            source="No secret/provider observation",
            detail="The referenced connection/secret has not been resolved or tested.",
            next_action="Resolve the secret reference through the approved local/runtime secret mechanism, then verify the connection with a read-only check.",
        ))
        actions.append(BootstrapAction(
            id="resolve-telemetry-connection",
            category="Connections",
            title="Resolve telemetry connection reference",
            kind="user-action",
            executable=False,
            reason="Secret material stays outside the project manifest and cannot be auto-filled by Studio.",
        ))
    else:
        checks.append(_check(
            "telemetry.connection-availability",
            "Connections",
            "Telemetry connection",
            "not_applicable",
            required=False,
            evidence_kind="local-contract",
            source="project contract",
            detail="This project does not declare telemetry configuration.",
        ))

    checks.append(_check(
        "monitoring.workspace",
        "Monitoring",
        "Workspace monitoring",
        "unknown",
        required=False,
        evidence_kind="none",
        source="No provider observation",
        detail="Monitoring configuration and health have not been observed.",
        next_action="Inspect workspace monitoring after the target workspace has been positively identified.",
    ))
    actions.append(BootstrapAction(
        id="observe-monitoring",
        category="Monitoring",
        title="Inspect workspace monitoring",
        kind="read",
        executable=False,
        reason="Monitoring state is not inferred from project configuration.",
    ))

    counts = {
        "satisfied": sum(check.status == "satisfied" for check in checks),
        "action_required": sum(check.status == "action_required" for check in checks),
        "unknown": sum(check.status == "unknown" for check in checks),
        "blocked": sum(check.status == "blocked" for check in checks),
        "not_applicable": sum(check.status == "not_applicable" for check in checks),
    }
    runtime_unresolved = any(
        check.required and check.status in {"unknown", "action_required", "blocked"}
        for check in checks
    )

    return ProjectReadinessReport(
        project_id=project["projectId"],
        profile_name=profile_name,
        workspace_display_name=profile["workspaceDisplayName"],
        evaluated_at=evaluated_at,
        deployable=False,
        authorization=False,
        summary="Runtime readiness is unresolved." if runtime_unresolved else "Local checks are satisfied, but M03 still does not grant deployment authorization.",
        counts=counts,
        checks=checks,
        bootstrap_actions=actions,
    )
