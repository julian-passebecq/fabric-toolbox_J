# Fabric Ops Studio backend

The backend is deliberately thin. It discovers and describes upstream capabilities; it does not copy their implementation.

## Current milestone

- FastAPI health endpoint
- capability catalog endpoint
- automatic discovery of public `MicrosoftFabricMgmt` PowerShell commands
- source path and provider metadata
- heuristic read/write/admin/destructive risk classification
- inspect-only execution preview

Execution is intentionally disabled until provider-specific validation, confirmation and activity logging are implemented.

## Run

```powershell
cd studio/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
fabric-ops-studio-api
```

Then open `http://127.0.0.1:8765/docs` for the API schema.

## Maintenance model

The discovery process scans `tools/MicrosoftFabricMgmt/source/Public/**/*.ps1` at runtime. When upstream adds public command files, they automatically become visible in `/api/capabilities` without copying those commands into Studio.

Curated metadata can override generated entries in `frontend/src/data/capabilities.json`.
