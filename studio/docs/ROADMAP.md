# Fabric Ops Studio roadmap

## Milestone 1 - inspect foundation

- [x] product scope and exclusions
- [x] provenance/source registry
- [x] Fluent UI shell
- [x] PowerShell Library surface
- [x] automatic MicrosoftFabricMgmt command discovery
- [x] inspect-only capability API
- [x] Windows launcher
- [ ] capability discovery tests
- [ ] connect frontend catalog to backend API instead of static fallback

## Milestone 2 - read-only operations

- workspace inventory
- item inventory by workspace and type
- capacities and workspace assignments
- connections inventory
- job/run history
- schedule inventory
- deployment pipeline inventory
- Git status inventory
- activity log

Only read-only commands are executable in this milestone.

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
