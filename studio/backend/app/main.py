from fastapi import FastAPI, HTTPException, Header

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
from .boundary import local_boundary

app = FastAPI(
    title="Fabric Ops Studio API",
    version="0.8.0",
    description="Fabric operations layer with read execution and explicitly allowlisted guarded writes.",
)
app.middleware('http')(local_boundary)


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


def _execute_read(item: Capability, parameters: dict, expected=None) -> dict:
    if item.risk != "read" or item.execution_policy != "read":
        raise UnsafeOperation("The direct executor accepts registered read operations only")
    if item.provider == "MicrosoftFabricMgmt":
        return runtime.execute_read(item, parameters, expected=expected)
    if item.provider == "Fabric REST API":
        return execute_rest_read(item, parameters, expected=expected)
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
def execute(capability_id: str, request: PreviewRequest | None = None, x_studio_session: str | None = Header(default=None)) -> ExecutionResult:
    item = _capability_or_404(capability_id)
    parameters = request.parameters if request else {}

    expected = runtime.status()
    if x_studio_session != expected.generation:
        raise HTTPException(status_code=409, detail='Session generation changed; refresh the connected context')
    if not expected.connected:
        raise HTTPException(status_code=409, detail="Connect to a Fabric tenant before executing operations")

    try:
        if item.risk != "read" or item.execution_policy != "read":
            raise UnsafeOperation("Writes cannot use the direct executor; create a guarded mutation plan instead")
        rendered, transport = _build_preview_command(item, parameters)
        result = _execute_read(item, parameters, expected)
    except (UnsafeOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


    return ExecutionResult(
        capability_id=item.id,
        provider=item.provider,
        risk=item.risk,
        rendered_command=rendered,
        result=result,
    )


@app.post("/api/capabilities/{capability_id}/mutations/plan", response_model=MutationPlan)
def create_mutation_plan(capability_id: str, request: MutationPlanRequest | None = None, x_studio_session: str | None = Header(default=None)) -> MutationPlan:
    item = _capability_or_404(capability_id)
    parameters = request.parameters if request else {}
    expected = runtime.status()
    if x_studio_session != expected.generation:
        raise HTTPException(status_code=409, detail='Session generation changed; refresh the connected context')
    try:
        plan = broker.create_plan(item, parameters, expected=expected)
    except (UnsafeOperation, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
