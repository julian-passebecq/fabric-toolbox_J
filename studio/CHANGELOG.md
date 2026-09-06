# Studio changelog

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
