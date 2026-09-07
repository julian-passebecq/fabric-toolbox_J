# Fabric Ops Studio roadmap

## Milestone 1 - inspect foundation

- [x] product scope and exclusions
- [x] provenance/source registry
- [x] Fluent UI shell
- [x] PowerShell Library surface
- [x] automatic MicrosoftFabricMgmt command discovery
- [x] PowerShell parameter/type/help discovery
- [x] capability discovery and safety tests
- [x] frontend catalog connected to backend API with static fallback
- [x] Windows launcher
- [x] local runtime diagnostics page
- [x] Windows launcher syntax validation in CI

## Milestone 2 - read-only operations

- [x] interactive Fabric tenant authentication through `Connect-FabricAccount`
- [x] persistent session status exposed to the UI
- [x] workspace inventory
- [x] shared workspace context with automatic `WorkspaceId` / `workspaceId` form prefilling
- [x] workspace role-assignment inspection through upstream cmdlet
- [x] workspace capacity assignment visible in workspace inventory
- [x] generic item inventory by workspace, with optional type/root-folder filters
- [x] generic item detail lookup
- [x] item connection inventory
- [x] capacity inventory
- [x] connections inventory
- [x] item job/run history
- [x] schedule inventory
- [x] deployment pipeline inventory/stages/operations through upstream cmdlets
- [x] workspace Git connection discovery through upstream cmdlet
- [x] workspace Git status through the official REST API
- [x] generic Fabric long-running-operation support by delegating `-WaitForCompletion` to MicrosoftFabricMgmt
- [x] reusable tabular/raw JSON result viewer with copy/download
- [x] local activity log with sensitive-field redaction
- [x] registered official Fabric REST GET provider via `Invoke-FabricAPIRequest`
- [x] backend enforcement that execution requires an authenticated Studio session

Fabric REST endpoints remain explicitly registered; arbitrary URLs and arbitrary HTTP methods are not accepted.

## Milestone 3 - guarded writes

### Guarded-write contract

- [x] writes blocked by default even when auto-discovered from MicrosoftFabricMgmt
- [x] explicit `guarded-write` allowlist metadata
- [x] tenant-bound mutation plans
- [x] SHA-256 binding of capability + tenant + parameters + exact rendered command
- [x] ten-minute plan expiry
- [x] single-use plan state machine
- [x] typed confirmation text
- [x] upstream `SupportsShouldProcess` / `-WhatIf` validation when registered
- [x] read-back verification through existing read capabilities
- [x] mutation plan / validation / execution activity logging
- [x] Change Plans UI for current backend-session plans
- [x] diagnostics for read / guarded-write / blocked execution policies

### Enabled writes

- [x] create workspace through upstream `New-FabricWorkspace`
- [x] update workspace name/description through upstream `Update-FabricWorkspace`
- [x] enforce `WorkspaceName` or `WorkspaceDescription` before an update plan can be created

### Still blocked

- [ ] role assignment changes
- [ ] capacity assignment
- [ ] create/delete selected Fabric items
- [ ] job retry/cancel
- [ ] schedule create/update/delete
- [ ] Git connect/commit/update
- [ ] destructive workspace/item operations

Do not widen this list simply because a cmdlet is discoverable. A write should only become executable after its upstream semantics, confirmation behavior, verification path and rollback/blast-radius expectations have been reviewed.

## Milestone 4 - specialized tools

- [x] Fabric Security Audit provenance, prerequisites and upstream entrypoint surface
- [x] Fabric Assessment Tool provenance, prerequisites and `fat assess` workflow surface
- [x] Lineage Extractor notebook provenance, prerequisites and entrypoint surface
- [ ] guarded Security Audit launcher and report-bundle browser
- [ ] guarded Assessment launcher and output browser
- [ ] optional Fabric-notebook handoff workflow for Lineage Extractor
- [ ] monitoring entry points and operational summary page

Specialized tools keep their own authentication, dependency and output lifecycle. Studio should orchestrate them only where it can do so without copying their implementation or weakening their permission boundaries.

## Milestone 5 - operator ergonomics

- [x] persisted recent workspace contexts without storing credentials, scoped by Fabric tenant
- [x] workspace-scoped item context so item IDs can be selected once and reused in item details, connections, runs and schedules
- [x] selected item is invalidated automatically when workspace context changes
- [x] recent item selections stored per tenant + workspace, without credentials or tokens
- [x] inherited operation parameters and remaining mandatory inputs are visible before execution
- [x] result filtering/sorting and CSV export
- [x] saved operation favorites and per-page last selection in browser-local storage
- [x] persisted mutation history across backend restarts by reconstructing from the redacted activity log rather than persisting live approval plans
- [x] capability compatibility report after upstream merges
- [x] searchable/exportable activity log with JSON and JSONL output
- [x] lazy-loaded secondary UI modules and stable React/Fluent vendor chunking
- [ ] optional update check against upstream Fabric Toolbox and Fabric REST specifications

## Next high-value pass

- guarded Security Audit launcher plus report-bundle browser, preserving the upstream script and its permission boundary
- guarded Assessment launcher plus output browser, preserving `fat assess` as the execution source
- item/job drill-down from a returned run row into the relevant operation context
- compatibility baseline/diff between Studio versions rather than current-state audit only
- optional upstream update signal without auto-mutating the fork
- review job cancellation/retry semantics and idempotency before deciding whether either belongs in the guarded-write allowlist

## Non-goals

- DAX optimization
- semantic-model authoring
- report authoring
- Power BI visual authoring
