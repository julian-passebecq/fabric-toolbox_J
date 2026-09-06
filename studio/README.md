# Fabric Ops Studio

Fabric Ops Studio is a management and operations UI layered on top of the existing Microsoft Fabric Toolbox.

## Product scope

The Studio is intentionally focused on tasks that are cumbersome to perform repeatedly in the Fabric portal or directly from a terminal:

- tenant, capacity, workspace and item inventory
- workspace membership and access review
- Fabric item lifecycle operations
- Lakehouse, Warehouse, SQL Database, Notebook, Pipeline, Environment and other Fabric item management
- job runs, schedules and operational history
- deployment pipeline operations
- Git workspace operations
- connection inventory and management
- security audits and effective-access troubleshooting
- migration/assessment workflows
- lineage and impact inspection
- monitoring entry points and operational summaries
- a searchable PowerShell recipe/script catalog
- safe execution of PowerShell and Fabric REST operations

## Explicitly out of scope

The following are deliberately excluded from the Studio product surface:

- DAX authoring or optimization
- semantic-model authoring
- Tabular model editing
- measure editing
- report canvas authoring
- visual authoring
- replacement of Tabular Editor
- replacement of DAX Studio
- replacement of Power BI Desktop

Reports and semantic models may still appear in inventory, lineage, permissions, Git, deployment and operational views because they are Fabric items. The Studio does not edit their analytical content.

## Primary execution hierarchy

Prefer the highest maintainability source available:

1. `MicrosoftFabricMgmt` PowerShell module in this repository
2. official Fabric REST API where the PowerShell module does not yet expose an operation
3. existing Fabric Toolbox scripts/tools where they solve a specialized workflow
4. small Studio-owned orchestration only when no upstream implementation exists

The UI must not duplicate an upstream implementation simply to make it callable from React.

## Provenance rule

Every executable feature must have a source declaration in `sources/source-registry.yaml` and expose its origin in the UI.

A feature record should make it possible to answer:

- Where does this capability come from?
- Is it Microsoft, Fabric Toolbox, community, or Studio-owned?
- Which repository/path implements it?
- Which API does it call?
- What license applies?
- Is it vendored, wrapped, linked, or Studio-owned?
- How is it updated?
- Is it preview/beta/stable?
- Is the operation read-only, write, admin, or destructive?

## UI principle

The UI is an operations console, not a black box.

For an operation such as creating a SQL Database, users should be able to see:

- the friendly form
- the PowerShell command/recipe being used
- the underlying REST endpoint when relevant
- required permissions/prerequisites
- source/provenance
- a preview of the request
- the execution result and logs

This keeps the Studio useful for both operators and people learning Fabric automation.

## Proposed top-level navigation

- Overview
- Workspaces
- Items
- Runs & Schedules
- Capacities
- Connections
- Deployment & Git
- Security
- Assessment
- Lineage
- Monitoring
- PowerShell Library
- Activity Log
- Sources

## Branch strategy

`main` should remain close to `microsoft/fabric-toolbox` so upstream updates are easy to merge.

Studio development lives independently under `studio/` and should avoid modifying upstream tool directories unless an upstream fix is intentionally being prepared.

Current development branch: `fabric-ops-studio-v1`.
