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
- safe execution of registered PowerShell and Fabric REST operations

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

## Current safety model

Studio uses an explicit three-state execution policy:

- `read`: registered read-only operations may execute after Fabric authentication.
- `guarded-write`: only individually reviewed writes may be planned, validated, confirmed and executed.
- `blocked`: all other write/admin/destructive capabilities remain non-executable even if discovered in the catalog.

Additional controls:

- `MicrosoftFabricMgmt` public commands are discovered automatically from `tools/MicrosoftFabricMgmt/source/Public`.
- Official Fabric REST operations must be registered explicitly with their endpoint and parameter schema; there is no arbitrary URL box.
- Fabric APIs that return `202 Accepted` declare `response_mode: fabric-lro` and delegate waiting/result retrieval to upstream `Invoke-FabricAPIRequest -WaitForCompletion`.
- Guarded writes are tenant-bound, expire after ten minutes, are single use and are cryptographically bound to the capability, tenant, parameters and rendered command.
- When the upstream cmdlet exposes `SupportsShouldProcess`, Studio requires `-WhatIf` validation before apply.
- Guarded writes require exact typed confirmation and use read-back verification where a verification capability is registered.
- Live mutation plans and approval text remain memory-only. Durable history is reconstructed from the redacted activity log rather than restoring reusable approvals after restart.
- Sensitive fields are redacted from local activity records.
- Specialized tools keep separate execution boundaries when they require additional authentication, permissions, dependencies or output lifecycles.

### Currently allowlisted writes

Only these writes are executable through the guarded-write broker:

- create workspace via upstream `New-FabricWorkspace`
- update workspace name/description via upstream `Update-FabricWorkspace`

Role changes, capacity assignment, item lifecycle writes, job cancellation/retry, schedule writes, Git writes and destructive operations remain blocked until their semantics, validation path, verification strategy and blast radius have been reviewed.

## Primary execution hierarchy

Prefer the highest-maintainability source available:

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
- Is it vendored, wrapped, linked, or Studio-owned?
- How is it updated?
- Is it read-only, write, admin, or destructive?
- What component actually executes it?

## Operator workflow

1. Start Studio.
2. Connect to a Fabric tenant with the tenant ID.
3. Open **Workspaces** and refresh the live inventory.
4. Select **Use workspace** on a workspace card. Recent workspace choices are remembered locally per tenant without credentials.
5. Open **Items**. The selected workspace ID is injected automatically; select **Use item** once to establish item context.
6. Item details, connections, runs and schedules inherit `workspaceId` and `itemId`. Changing workspace invalidates the selected item so an item ID cannot leak across workspace context.
7. Operation pages show inherited parameters explicitly and identify mandatory parameters that still need operator input, such as `jobType`.
8. Preview generated PowerShell/REST execution when desired. Read operations can execute directly; allowlisted writes use Change Plans and the guarded-write broker.
9. Inspect results as a sortable/filterable table or raw JSON. Export JSON or CSV as appropriate.
10. Use **Change Plans**, **Activity Log**, **Sources** and **Diagnostics** to inspect approvals, execution history, provenance and runtime/compatibility health.

## Local Windows launch

Prerequisites:

- PowerShell 7 (`pwsh`)
- Python available as `python`
- Node.js and npm

From the repository root:

```powershell
.\studio\scripts\start-studio.ps1
```

Useful flags:

```powershell
# Do not open the browser automatically
.\studio\scripts\start-studio.ps1 -NoBrowser

# Skip Python/npm installation when dependencies are already present
.\studio\scripts\start-studio.ps1 -SkipInstall
```

The launcher starts the API and UI in separate PowerShell 7 windows, then opens `http://127.0.0.1:5173` unless `-NoBrowser` is used.

## Current top-level navigation

- Overview
- Workspaces
- Change Plans
- Items
- Runs & Schedules
- Capacities
- Connections
- Deployment & Git
- Security
- Assessment
- Lineage
- PowerShell Library
- Diagnostics
- Activity Log
- Sources

Security, Assessment and Lineage currently expose their upstream workflow, prerequisites and entrypoint. They are not flattened into the generic capability executor.

## UI principle

The UI is an operations console, not a black box.

For each operation, users should be able to see as applicable:

- the friendly/generated parameter form
- inherited workspace/item context
- mandatory context still missing
- the PowerShell command or execution wrapper being used
- the underlying REST endpoint
- long-running-operation behavior
- required permissions/prerequisites
- source/provenance
- a preview of the request
- mutation-plan state for writes
- execution result and logs

This keeps Studio useful for operators while also making Fabric automation understandable and maintainable.

## Maintenance and compatibility

Studio-owned code stays under `studio/` so `main` can remain close to `microsoft/fabric-toolbox`.

Diagnostics includes a catalog compatibility audit that checks duplicate capability IDs, broken verification references, guarded-write policy inconsistencies, malformed registered REST endpoints and missing repository-local source paths. Run it after upstream merges before widening any execution permissions.

The frontend lazy-loads secondary pages and separates React/Fluent dependencies into cacheable vendor chunks so new operator modules do not continuously inflate the initial application bundle.

## Branch strategy

`main` should remain close to `microsoft/fabric-toolbox` so upstream updates are easy to merge.

Studio development lives independently under `studio/` and should avoid modifying upstream tool directories unless an upstream fix is intentionally being prepared.

Current development branch: `fabric-ops-studio-v1`.
