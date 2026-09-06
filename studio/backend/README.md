# Fabric Ops Studio backend

The backend is deliberately thin. It discovers, validates and invokes upstream capabilities; it does not copy their domain implementation.

## Current milestone: guarded read-only operations

Implemented:

- FastAPI health/session endpoints
- automatic discovery of public `MicrosoftFabricMgmt` PowerShell commands
- comment-help synopsis and parameter discovery
- source path and provider metadata
- read/write/admin/destructive risk classification
- curated metadata overrides for important operations
- interactive `Connect-FabricAccount` tenant authentication
- read-only `MicrosoftFabricMgmt` execution
- parameter allowlisting and PowerShell literal escaping
- execution preview with the exact rendered PowerShell command
- local activity logging with sensitive-field redaction
- source/provenance registry API

Write, admin and destructive operations remain blocked by the generic executor.

## Feature source vs execution transport

Studio intentionally records these separately:

- **Feature provider:** `tools/MicrosoftFabricMgmt` and the cmdlet being executed.
- **Execution transport:** `tools/MicrosoftFabricMgmtMCPServer/core/powershell_session.py`.
- **Studio-owned layer:** discovery metadata, validation, safety policy, HTTP API, activity logging and UI.

The persistent PowerShell session is dynamically imported from the existing upstream management MCP implementation. Studio does not maintain a copied fork of that session code.

## Run

From the repository root on Windows:

```powershell
.\studio\scripts\start-studio.ps1
```

Or run the backend directly:

```powershell
cd studio/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
fabric-ops-studio-api
```

Then open `http://127.0.0.1:8765/docs` for the API schema. The frontend development server uses `http://127.0.0.1:5173` and proxies `/api` to the backend.

## Maintenance model

The discovery process scans `tools/MicrosoftFabricMgmt/source/Public/**/*.ps1` at runtime. When upstream adds public command files, they automatically become visible in `/api/capabilities` without copying those commands into Studio.

Curated metadata can override generated entries in `frontend/src/data/capabilities.json`. Upstream implementations should remain unmodified; Studio adapters should stay thin.

## Safety boundary

Only capabilities with:

- provider `MicrosoftFabricMgmt`, and
- risk classification `read`

can currently pass the generic execution guard. Unknown parameters are rejected before PowerShell execution. Mutating commands are covered by backend tests and will be enabled later only through explicit provider-specific guarded workflows.
