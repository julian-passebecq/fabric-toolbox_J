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

## Milestone 2 - read-only operations

- [x] interactive Fabric tenant authentication through `Connect-FabricAccount`
- [x] workspace inventory
- [x] generic item inventory by workspace, with optional type/root-folder filters
- [x] capacity inventory
- [x] connections inventory
- [x] item job/run history
- [x] schedule inventory
- [x] deployment pipeline inventory/stages/operations through upstream cmdlets
- [x] workspace Git connection discovery through upstream cmdlet
- [x] local activity log with sensitive-field redaction
- [x] registered official Fabric REST GET provider via `Invoke-FabricAPIRequest`
- [ ] workspace-to-capacity assignment inventory/detail view
- [ ] Git status inventory
- [ ] generic long-running-operation support for REST APIs returning `202 Accepted`
- [ ] richer tabular result viewer for REST responses

Only read-only operations are executable in this milestone. Git status is deliberately deferred because the official API can return a long-running operation and Studio does not yet pretend that a simple GET wrapper handles that correctly.

## Milestone 3 - guarded writes

- create/update workspace
- role assignment changes
- capacity assignment
- create/delete selected Fabric items
- job retry/cancel
- schedule create/update/delete
- Git connect/commit/update

All writes require preview, validation and activity logging. Destructive operations require stronger confirmation.

## Milestone 4 - specialized tools

- Fabric Security Audit wrapper
- Fabric Assessment Tool wrapper
- operational Lineage Extractor integration
- monitoring entry points and result browser

## Non-goals

- DAX optimization
- semantic-model authoring
- report authoring
- Power BI visual authoring
