# Studio changelog

## 0.11.0

- Added a generated Foil'o `eventstream.json` artifact that follows the current Microsoft Fabric Eventstream definition topology model.
- Added two Foil'o ingestion modes: Fabric Custom Endpoint for the default outbound Oracle design, and Apache Kafka source through a registered Fabric connection.
- Added explicit Kafka connection/consumer-group and KQL destination-table project parameters.
- Added Eventstream artifact preview/copy in Project Composer with live dependency checks for workspace, Eventhouse and KQL Database.
- Added content-bound mutation artifacts for upstream file-based Fabric cmdlets. Artifact bytes are SHA-256 bound to the mutation plan, materialized under a plan-scoped temporary directory, verified before WhatIf and execution, and cleaned after terminal execution.
- Restricted artifact binding to reviewed upstream `*PathDefinition` / `*PathPlatformDefinition` parameters with filename/path and size guardrails.
- Project Composer now attaches the generated `eventstream.json` automatically when staging a dependency-ready Eventstream create plan.
- Change Plans now exposes validation and guarded execution controls for Composer-staged plans, including exact confirmation text and bound-artifact SHA visibility.
- Added regression coverage for artifact tampering, path traversal, cleanup and Eventstream topology generation.


## 0.10.0

- Added guarded provisioning for KQL Database through upstream `New-FabricKQLDatabase`, including explicit ReadWrite/Shortcut type validation, parent Eventhouse binding and name-based read-back verification.
- Added guarded provisioning for KQL Dashboard through upstream `New-FabricKQLDashboard` with the existing WhatIf, typed-approval and read-back safety contract.
- Extended Foil'o Project Composer plans with provisioning capability IDs, exact upstream parameters, readiness state and dependency reasons.
- Added dependency-aware deployment waves: Composer only stages create plans when the target workspace exists and all declared dependencies are already present in Fabric.
- Resolved the live parent Eventhouse Fabric item ID into `parentEventhouseId` for the Foil'o `wind_telemetry` KQL database.
- Added Composer staging into the existing Change Plans broker. Staging creates tenant-bound mutation plans only; it never executes Fabric changes directly.
- Preserved unmanaged workspace items and conflicts as non-mutating plan states.
- Added regression coverage for KQL Database/Dashboard guarded commands, parent binding and first/next Foil'o provisioning waves.

## 0.9.0

- Added a dedicated Guarded Provisioning surface for selected Fabric item creation.
- Explicitly allowlisted upstream MicrosoftFabricMgmt create cmdlets for Eventhouse, Eventstream, KQL Queryset, Lakehouse, Notebook, Environment and Data Pipeline.
- Preserved the existing tenant-bound, expiring, single-use mutation plan and typed-approval model for every new create.
- Required upstream SupportsShouldProcess / -WhatIf validation and registered name-based read-back verification for every newly enabled item type.
- Fixed PowerShell parameter rendering so Boolean value parameters such as LakehouseEnableSchemas render as $true/$false while switch parameters retain switch semantics.
- Added fail-fast validation for upstream mandatory parameters and ValidateSet values before PowerShell execution.
- KQL Database and KQL Dashboard were intentionally left gated in v0.9 and are enabled in v0.10 after dependency/read-back review.


## 0.8.0

- Added the first Project Composer milestone for declarative Fabric project architecture.
- Added the Foil'o Wind Energy Real-Time Intelligence template covering Eventhouse, KQL Database, Eventstream, KQL Queryset, KQL Dashboard, Lakehouse, Environment, Notebooks and a Data Pipeline.
- Added live diff planning against a selected Fabric workspace using the existing registered Items read API.
- Added explicit plan actions for create, unchanged, name/type conflict and unmanaged existing items.
- Preserved unmanaged workspace content; Composer never proposes implicit deletion.
- Added VS Code authoring handoff metadata for definition-heavy items.
- Added the Project Composer Fluent UI page and top-level navigation.
- Added backend/template tests for RTI coverage, dependency metadata, diff behavior, conflicts and unmanaged-item preservation.
- Kept Project Composer apply disabled. The guarded-write allowlist remains unchanged until each item-type create/update path has its own reviewed endpoint, validation and verification semantics.


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
