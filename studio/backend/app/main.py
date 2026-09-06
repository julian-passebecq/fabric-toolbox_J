from fastapi import FastAPI, HTTPException

from .catalog import combined_catalog
from .models import Capability, ExecutionPreview

app = FastAPI(
    title="Fabric Ops Studio API",
    version="0.1.0",
    description="Thin inspect-first orchestration layer over Fabric Toolbox providers.",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "inspect"}


@app.get("/api/capabilities", response_model=list[Capability])
def capabilities() -> list[Capability]:
    return combined_catalog()


@app.get("/api/capabilities/{capability_id}", response_model=Capability)
def capability(capability_id: str) -> Capability:
    for item in combined_catalog():
        if item.id == capability_id:
            return item
    raise HTTPException(status_code=404, detail="Capability not found")


@app.post("/api/capabilities/{capability_id}/preview", response_model=ExecutionPreview)
def preview(capability_id: str) -> ExecutionPreview:
    item = capability(capability_id)
    return ExecutionPreview(
        capability_id=item.id,
        provider=item.provider,
        risk=item.risk,
        command=item.command,
        endpoint=item.endpoint,
        executable=False,
        reason="Inspect-only milestone: execution will be enabled provider-by-provider after validation and audit logging are in place.",
    )


def run() -> None:
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=False)
