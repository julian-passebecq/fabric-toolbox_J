from fastapi import FastAPI, HTTPException

from .activity import append_activity, read_activity
from .catalog import combined_catalog
from .diagnostics import collect_diagnostics
from .models import (
    Capability,
    ConnectRequest,
    ExecutionPreview,
    ExecutionResult,
    MutationApprovalRequest,
    MutationExecutionResult,
    MutationPlan,
    MutationPlanRequest,
    MutationValidationResult,
    PreviewRequest,
    SessionStatus,
)
from .mutations import broker
from .providers.fabric_rest import build_rest_get_command, execute_rest_read
from .providers.microsoftfabricmgmt import (
    ProviderUnavailable,
    UnsafeOperation,
    build_guarded_write_command,
    build_read_command,
    runtime,
)
from .sources import load_source_registry
from .specialized_tools import list_specialized_tools

app = FastAPI(
    title="Fabric Ops Studio API",
    version="0.5.0",
    description="Fabric operations layer with read execution and explicitly allowlisted guarded writes.",
)


def _capability_or_404(capability_id: str) -> Capability:
    for item in combined_catalog():
        if item.id == capability_id:
            return item
    raise HTTPException(status_code=404, detail="Capability not found")


def _build_preview_command(item: Capability, parameters: dict) -> tuple[str, str]:
    if item.provider == "MicrosoftFabricMgmt":
        if item.risk == "read" and item.execution_policy == "read":
            return build_read_command(item, parameters), "tools/MicrosoftFabricMgmtMCPServer/core/powershell_session.py"
        if item.risk == "write" and item.execution_policy == "guarded-write":
            return build_guarded_write_command(item, parameters), "Studio guarded-write broker -> upstream persistent PowerShell session"
        raise UnsafeOperation(
            f"Capability is catalogued but not executable; risk={item.risk}, policy={item.execution_policy}"
        )
    if item.provider == "Fabric REST API" and item.risk == "read" and item.execution_policy == "read":
        return build_rest_get_command(item, parameters), "MicrosoftFabricMgmt.Invoke-FabricAPIRequest via upstream PowerShell session"
    raise UnsafeOperation(f"Provider is not executable in this milestone: {item.provider}")


def _execute_read(item: Capability, parameters: dict) -> dict:
    if item.risk != "read" or item.execution_policy != "read":
        raise UnsafeOperation("The direct executor accepts registered read operations only")
    if item.provider == "MicrosoftFabricMgmt":
        return runtime.execute_read(item, parameters)
    if item.provider == "Fabric REST API":
        return execute_rest_read(item, parameters)
    raise UnsafeOperation(f"Provider is not executable in this milestone: {item.provider}")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "guarded-writes"}


@app.get("/api/session", response_model=SessionStatus)
def session_status() -> SessionStatus:
    return runtime.status()


@app.post("/api/session/connect")
def connect(request: ConnectRequest) -> dict:
    try:
        result = runtime.connect_interactive(request.tenant_id)
        append_activity(
            {
                "action": "session.connect",
                "provider": "MicrosoftFabricMgmt",
                "transport": "upstream-powershell-session",
                "parameters": {"tenant_id": request.tenant_id},
                "result": result,
            }
        )
        return result
    except (ProviderUnavailable, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/capabilities", response_model=list[Capability])
def capabilities() -> list[Capability]:
    return combined_catalog()


@app.get("/api/capabilities/{capability_id}", response_model=Capability)
def capability(capability_id: str) -> Capability:
    return _capability_or_404(capability_id)


@app.post("/api/capabilities/{capability_id}/preview", response_model=ExecutionPreview)
def preview(capability_id: str, request: PreviewRequest | None = None) -> ExecutionPreview:
    item = _capability_or_404(capability_id)
    parameters = request.parameters if request else {}

    try:
        rendered, transport = _build_preview_command(item, parameters)
    except (UnsafeOperation, ValueError) as exc:
        return ExecutionPreview(
            capability_id=item.id,
            provider=item.provider,
            risk=item.risk,
            command=item.command,
            endpoint=item.endpoint,
            executable=False,
            reason=str(exc),
        )

    if item.execution_policy == "guarded-write":
        reason = (
            "Guarded write preview only. Create a tenant-bound mutation plan, run upstream -WhatIf validation, "
            "then type the plan confirmation text before the broker can execute it."
        )
    else:
        mode_note = " Fabric LRO completion is delegated to MicrosoftFabricMgmt." if item.response_mode == "fabric-lro" else ""
        reason = "Registered read-only operation; execution is enabled after interactive Fabric authentication." + mode_note

    return ExecutionPreview(
        capability_id=item.id,
        provider=item.provider,
        risk=item.risk,
        command=item.command,
        endpoint=item.endpoint,
        rendered_command=rendered,
        transport=transport,
        executable=True,
        reason=reason,
    )


@app.post("/api/capabilities/{capability_id}/execute", response_model=ExecutionResult)
def execute(capability_id: str, request: PreviewRequest | None = None) -> ExecutionResult:
    item = _capability_or_404(capability_id)
    parameters = request.parameters if request else {}

    if not runtime.status().connected:
        raise HTTPException(status_code=409, detail="Connect to a Fabric tenant before executing operations")

    try:
        if item.risk != "read" or item.execution_policy != "read":
            raise UnsafeOperation("Writes cannot use the direct executor; create a guarded mutation plan instead")
        rendered, transport = _build_preview_command(item, parameters)
        result = _execute_read(item, parameters)
    except (UnsafeOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    append_activity(
        {
            "action": "capability.execute",
            "capability_id": item.id,
            "provider": item.provider,
            "source": item.source,
            "source_path": item.source_path,
            "endpoint": item.endpoint,
            "response_mode": item.response_mode,
            "execution_policy": item.execution_policy,
            "transport": transport,
            "risk": item.risk,
            "rendered_command": rendered,
            "parameters": parameters,
            "result": result,
        }
    )

    return ExecutionResult(
        capability_id=item.id,
        provider=item.provider,
        risk=item.risk,
        rendered_command=rendered,
        result=result,
    )


@app.post("/api/capabilities/{capability_id}/mutations/plan", response_model=MutationPlan)
def create_mutation_plan(capability_id: str, request: MutationPlanRequest | None = None) -> MutationPlan:
    item = _capability_or_404(capability_id)
    parameters = request.parameters if request else {}
    try:
        plan = broker.create_plan(item, parameters)
    except (UnsafeOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    append_activity(
        {
            "action": "mutation.plan",
            "plan_id": plan.plan_id,
            "digest": plan.digest,
            "capability_id": item.id,
            "provider": item.provider,
            "source": item.source,
            "source_path": item.source_path,
            "risk": item.risk,
            "parameters": parameters,
            "rendered_command": plan.rendered_command,
            "expires_at": plan.expires_at,
        }
    )
    return plan


@app.get("/api/mutations", response_model=list[MutationPlan])
def mutation_plans() -> list[MutationPlan]:
    return broker.list()


@app.get("/api/mutations/{plan_id}", response_model=MutationPlan)
def mutation_plan(plan_id: str) -> MutationPlan:
    try:
        return broker.get(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/mutations/{plan_id}/validate", response_model=MutationValidationResult)
def validate_mutation(plan_id: str) -> MutationValidationResult:
    try:
        response = broker.validate(plan_id)
    except (UnsafeOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    append_activity(
        {
            "action": "mutation.validate",
            "plan_id": response.plan.plan_id,
            "digest": response.plan.digest,
            "capability_id": response.plan.capability_id,
            "status": response.plan.status,
            "result": response.result,
        }
    )
    return response


@app.post("/api/mutations/{plan_id}/execute", response_model=MutationExecutionResult)
def execute_mutation(plan_id: str, request: MutationApprovalRequest) -> MutationExecutionResult:
    try:
        response = broker.execute(plan_id, request.confirmation)
    except (UnsafeOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    append_activity(
        {
            "action": "mutation.execute",
            "plan_id": response.plan.plan_id,
            "digest": response.plan.digest,
            "capability_id": response.plan.capability_id,
            "provider": response.plan.provider,
            "risk": response.plan.risk,
            "status": response.plan.status,
            "rendered_command": response.plan.rendered_command,
            "parameters": response.plan.parameters,
            "result": response.result,
            "verification": response.verification,
        }
    )
    return response


@app.get("/api/activity")
def activity(limit: int = 200) -> list[dict]:
    return read_activity(limit)


@app.get("/api/sources")
def sources() -> dict:
    return load_source_registry()


@app.get("/api/tools")
def tools() -> list[dict]:
    return list_specialized_tools()


@app.get("/api/diagnostics")
def diagnostics() -> dict:
    return collect_diagnostics()


def run() -> None:
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=False)
