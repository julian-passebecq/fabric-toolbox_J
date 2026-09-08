# Studio changelog

## 0.8.0 — S01 reliability candidate

- Reviewed execution admission and shared typed input contracts.
- Versioned outcomes, session generation checks and bounded PowerShell lifecycle.
- Immutable plans, atomic claims and explicit uncertain/unverified outcomes.
- Per-launch local client boundary and bounded structured activity history.
- Context-safe UI, component/browser fixtures, locked installs and owned cleanup.
- Workspace writes suspended: upstream retry/204 defects require lead review.

Local evidence does not imply tenant validation or sprint acceptance.


## 0.7.0

- Added first-class item context on top of the existing tenant/workspace context model.
- Added a workspace-scoped Item Explorer: select one item and automatically reuse `workspaceId` + `itemId` across item detail, item connections, job instances and schedules.
- Automatically clear selected item context when workspace context changes so item IDs cannot leak across workspaces.
- Added tenant + workspace scoped recent-item memory in browser-local storage, with migration of the previous workspace-only recent-selection cache. No credentials, tokens or approval state are persisted.
- Generalized the inventory component to accept registered capability parameters, validate required context before execution and normalize common Fabric REST list payload shapes.
- Added explicit inherited-context badges on operation pages and badges for mandatory parameters still requiring operator input.
- Added item context to the global connection strip and Overview state summary.
- Added direct navigation from selected item context into Runs & Schedules.
- Lazy-loaded secondary pages so adding operator modules no longer inflates the initial application bundle.
- Split React and Fluent dependencies into stable vendor chunks. The application entry chunk dropped from roughly 504 kB in v0.6 to roughly 50 kB in the first v0.7 production build.
- Kept the guarded-write allowlist unchanged. Item, job, schedule, Git and destructive writes remain blocked.
- Refreshed README and roadmap documentation so they describe the actual guarded-write safety model and current navigation rather than the older read-only state.

## 0.6.0

- Added filtering, click-to-sort columns and CSV export to the reusable result viewer while retaining raw JSON, copy and JSON download.
- Added durable mutation history to Change Plans by reconstructing mutation events from the existing redacted activity log. Live approval plans remain memory-only and are never restored after restart.
- Added capability compatibility diagnostics for duplicate IDs, broken verification references, guarded-write policy inconsistencies, malformed registered Fabric REST endpoints and missing repository-local source paths.
- Added regression tests for compatibility failures and corrected diagnostics expectations for guarded-write runtime mode.
- Added browser-local operation favorites and per-page last-operation memory without storing credentials or approval state.
- Added tenant-scoped recent workspace selections using only workspace ID, display name and last-used timestamp in local storage.
- Added Activity Log search plus filtered JSON and JSONL export.
- Kept the guarded-write allowlist unchanged; this pass improves operator ergonomics and auditability rather than widening mutation authority.

## 0.5.0

- Added an explicit `guarded-write` execution policy while keeping unreviewed writes/admin/destructive capabilities blocked.
- Added tenant-bound mutation plans with ten-minute expiry and single-use lifecycle states.
- Bound each plan to capability ID, tenant, exact parameters and rendered command using SHA-256.
- Added typed confirmation text and required validation before execution where the upstream cmdlet exposes `SupportsShouldProcess` / `-WhatIf`.
- Added post-execution read-back verification through existing read capabilities where configured.
- Added mutation planning, validation and execution events to the redacted activity log.
- Added the Change Plans UI for current backend-session plans.
- Enabled only two reviewed workspace mutations: create workspace and update workspace name/description through upstream MicrosoftFabricMgmt cmdlets.
- Added parameter guardrails for workspace updates so at least name or description must be supplied.
- Left role assignment, capacity assignment, item lifecycle, job/schedule writes, Git writes and destructive operations blocked.

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
