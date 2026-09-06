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
from .providers.microsoftfabricmgmt import (
    ProviderUnavailable,
    UnsafeOperation,
    build_read_command,
    runtime,
)
from .sources import load_source_registry

app = FastAPI(
    title="Fabric Ops Studio API",
    version="0.2.0",
    description="Thin read-only operations layer over Fabric Toolbox providers.",
)


def _capability_or_404(capability_id: str) -> Capability:
    for item in combined_catalog():
        if item.id == capability_id:
            return item
    raise HTTPException(status_code=404, detail="Capability not found")


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

    if item.provider == "MicrosoftFabricMgmt" and item.risk == "read" and item.command:
        try:
            rendered = build_read_command(item, parameters)
        except (UnsafeOperation, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ExecutionPreview(
            capability_id=item.id,
            provider=item.provider,
            risk=item.risk,
            command=item.command,
            endpoint=item.endpoint,
            rendered_command=rendered,
            transport="tools/MicrosoftFabricMgmtMCPServer/core/powershell_session.py",
            executable=True,
            reason="Read-only MicrosoftFabricMgmt operation; execution is enabled after interactive Fabric authentication.",
        )

    return ExecutionPreview(
        capability_id=item.id,
        provider=item.provider,
        risk=item.risk,
        command=item.command,
        endpoint=item.endpoint,
        executable=False,
        reason="Only read-only MicrosoftFabricMgmt capabilities are executable in this milestone.",
    )


@app.post("/api/capabilities/{capability_id}/execute", response_model=ExecutionResult)
def execute(capability_id: str, request: PreviewRequest | None = None) -> ExecutionResult:
    item = _capability_or_404(capability_id)
    parameters = request.parameters if request else {}

    try:
        rendered = build_read_command(item, parameters)
        result = runtime.execute_read(item, parameters)
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
