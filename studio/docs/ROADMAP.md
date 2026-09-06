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

Only read-only operations are executable in this milestone. Fabric REST endpoints remain explicitly registered; arbitrary URLs and arbitrary HTTP methods are not accepted.

## Milestone 3 - guarded writes

- [ ] create/update workspace
- [ ] role assignment changes
- [ ] capacity assignment
- [ ] create/delete selected Fabric items
- [ ] job retry/cancel
- [ ] schedule create/update/delete
- [ ] Git connect/commit/update

All writes require preview, validation and activity logging. Destructive operations require stronger confirmation. This milestone should introduce a separate guarded-write contract rather than weakening the read-only executor.

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

- [ ] persisted recent workspace contexts without storing credentials
- [ ] richer item-to-run navigation so item IDs can be selected rather than pasted
- [ ] result filtering/sorting and CSV export
- [ ] saved read-only recipes/favorites
- [ ] capability compatibility report after upstream merges
- [ ] optional update check against upstream Fabric Toolbox and Fabric REST specifications

## Non-goals

- DAX optimization
- semantic-model authoring
- report authoring
- Power BI visual authoring
