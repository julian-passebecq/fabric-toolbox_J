from fastapi import FastAPI, HTTPException

from .activity import append_activity, read_activity
from .catalog import combined_catalog
from .models import (
    Capability,
    ConnectRequest,
    ExecutionPreview,
    ExecutionResult,
    PreviewRequest,
    SessionStatus,
)
from .providers.fabric_rest import build_rest_get_command, execute_rest_read
from .providers.microsoftfabricmgmt import (
    ProviderUnavailable,
    UnsafeOperation,
    build_read_command,
    runtime,
)
from .sources import load_source_registry

app = FastAPI(
    title="Fabric Ops Studio API",
    version="0.3.0",
    description="Thin read-only operations layer over Fabric Toolbox and registered Fabric REST providers.",
)


def _capability_or_404(capability_id: str) -> Capability:
    for item in combined_catalog():
        if item.id == capability_id:
            return item
    raise HTTPException(status_code=404, detail="Capability not found")


def _build_preview_command(item: Capability, parameters: dict) -> tuple[str, str]:
    if item.provider == "MicrosoftFabricMgmt":
        return build_read_command(item, parameters), "tools/MicrosoftFabricMgmtMCPServer/core/powershell_session.py"
    if item.provider == "Fabric REST API":
        return build_rest_get_command(item, parameters), "MicrosoftFabricMgmt.Invoke-FabricAPIRequest via upstream PowerShell session"
    raise UnsafeOperation(f"Provider is not executable in this milestone: {item.provider}")


def _execute_read(item: Capability, parameters: dict) -> dict:
    if item.provider == "MicrosoftFabricMgmt":
        return runtime.execute_read(item, parameters)
    if item.provider == "Fabric REST API":
        return execute_rest_read(item, parameters)
    raise UnsafeOperation(f"Provider is not executable in this milestone: {item.provider}")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "read-only"}


@app.get("/api/session", response_model=SessionStatus)
def session_status() -> SessionStatus:
    return SessionStatus()


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

    return ExecutionPreview(
        capability_id=item.id,
        provider=item.provider,
        risk=item.risk,
        command=item.command,
        endpoint=item.endpoint,
        rendered_command=rendered,
        transport=transport,
        executable=True,
        reason="Registered read-only operation; execution is enabled after interactive Fabric authentication.",
    )


@app.post("/api/capabilities/{capability_id}/execute", response_model=ExecutionResult)
def execute(capability_id: str, request: PreviewRequest | None = None) -> ExecutionResult:
    item = _capability_or_404(capability_id)
    parameters = request.parameters if request else {}

    try:
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


@app.get("/api/activity")
def activity(limit: int = 200) -> list[dict]:
    return read_activity(limit)


@app.get("/api/sources")
def sources() -> dict:
    return load_source_registry()


def run() -> None:
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=False)
