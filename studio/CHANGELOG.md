# Studio changelog

## 0.4.0

- Added declarative Fabric long-running-operation support for registered REST reads.
- Reused `MicrosoftFabricMgmt Invoke-FabricAPIRequest -WaitForCompletion` and the upstream operation/result helpers instead of implementing a Studio polling loop.
- Added official workspace Git status as an LRO-aware read operation.
- Added generic item detail and item-connection reads.
- Added workspace role-assignment inspection through the upstream `Get-FabricWorkspaceRoleAssignment` cmdlet.
- Added shared workspace context: select a workspace once and generated PowerShell/REST forms inherit `WorkspaceId` / `workspaceId` automatically.
- Added persistent backend session state and restored it in the frontend after page reloads while the backend process remains alive.
- Added backend enforcement that read execution requires an authenticated Studio session.
- Added a reusable result viewer with automatic table detection, raw JSON, copy and JSON download.
- Added a Diagnostics page for PowerShell, Python, upstream module/session, Azure CLI and specialized-tool readiness.
- Added explicit specialized-tool surfaces for Fabric Security Audit, Fabric Assessment Tool and Lineage Extractor, including prerequisites, upstream paths and entrypoints.
- Kept Security Audit and Assessment execution preview-only and Lineage notebook-driven rather than flattening their authentication/dependency models into the generic executor.
- Expanded source provenance with explicit LRO transport and specialized-tool execution boundaries.
- Added tests for LRO rendering, item detail/connections, diagnostics and specialized-tool registry behavior.
- Added a Windows CI job that parses `start-studio.ps1` with PowerShell 7.
- Hardened the Windows launcher with prerequisite checks, separate backend/frontend PowerShell 7 processes, optional browser launch and `-SkipInstall` / `-NoBrowser` flags.
- Preserved the npm workspace-root install model under `studio/package.json`.

## 0.3.0

- Added guarded read-only execution for `MicrosoftFabricMgmt` cmdlets.
- Reused the upstream persistent PowerShell session instead of copying its process/session implementation.
- Added interactive Fabric authentication through `Connect-FabricAccount`.
- Added automatic PowerShell parameter/type/help discovery and generated read-only forms.
- Added workspace, capacity and connection inventory surfaces.
- Added a registered Fabric REST GET provider that executes through upstream `Get-FabricAPIHeaders` and `Invoke-FabricAPIRequest`.
- Registered official Items, Job Instances and Schedules read endpoints with explicit parameter schemas.
- Added Items and Runs & Schedules operation pages.
- Added read-only deployment-pipeline and workspace Git-connection operations from upstream cmdlets.
- Added local activity logging with sensitive-field redaction.
- Expanded Sources to separate feature provider, execution transport and update strategy.
- Added backend safety tests for PowerShell and REST paths and frontend/backend CI.
- Kept all write/admin/destructive generic operations blocked.
- Deferred Git status until Fabric long-running-operation handling is implemented.

## 0.1.0

- Created Fabric Ops Studio as a separate management/operations surface.
- Excluded DAX, report authoring and semantic-model authoring.
- Added source/provenance registry.
- Added Fluent UI application shell.
- Added PowerShell Library and Sources views.
- Added inspect-first FastAPI backend.
- Added automatic discovery of `MicrosoftFabricMgmt` public PowerShell commands.
- Added initial risk classification and preview-only execution contract.
- Added Windows `start-studio.ps1` launcher.
