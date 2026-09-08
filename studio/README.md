# Fabric Ops Studio

Fabric Ops Studio is a management and operations UI layered on top of the existing Microsoft Fabric Toolbox.

## Product direction (some features remain future work)

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
- explicitly reviewed execution of selected PowerShell and Fabric REST reads

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

## Current execution boundary (S01 candidate)

S01 is awaiting a tech-lead decision, not accepted or tenant-validated.
Workspace create/update are **blocked**: the upstream API helper retries uncertain
POST/PATCH responses and rejects HTTP 204. See the developer handoff under
`projectmanagement/reports/S01-development-handoff.md` for the reproduced defect
and proposed upstream repair. No other writes are enabled.

The reviewed read subset is workspace, workspace roles, capacity and connection
inventory, plus six registered REST GETs for items, item details/connections,
runs, schedules and Git status. All other discoveries remain visible but blocked.
Backend `admission.json` binds the reviewed source and parameter contract; source
or contract drift cannot silently gain permission. Loaded function ASTs and module
file identity are checked against repository sources before dispatch.

Candidate broker behavior is tested with harmless fixtures: immutable detached
plans bind tenant, session generation, loaded artifact, parameters, exact commands,
verification contract and ten-minute expiry. Validation/apply claims are atomic.
An apply is single-use. WhatIf is a local simulation, not remote permission proof.
Create verification requires the returned unique ID; update verification compares
requested fields at the requested ID. Outcomes distinguish `executed`,
`applied_unverified`, `failed` and `outcome_unknown`. Inspect remote state after an
unknown outcome; do not replay a write. Production write admission has no runtime
or environment override. Only test fixtures lift the suspension without real I/O.

The launcher creates a fresh server-side client credential. Backend and Vite both
check Host/Origin; Vite replaces any client-supplied credential. The credential is
never placed in a URL, browser storage or bundle. Both services bind to loopback.
A manually started backend without its credential rejects protected routes. One
backend worker is supported; the boundary is not isolation from the same OS user.

History stores structured action/status/UUID/timing summaries, not parameter
values, commands or provider text. It uses 4 KiB records, 10 MiB files, five rotated
files, a 1 MiB read budget and at most 1,000 returned records. Legacy records are
sanitized on read. A start without an outcome from an earlier process is unknown.
Mutation start-log failure blocks dispatch; outcome-log failure retains the
terminal result and adds a warning. History never recreates approvals.

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
8. Preview generated PowerShell/REST execution when desired. Reviewed read operations can execute directly; workspace writes are currently blocked pending the lead decision.
9. Inspect results as a sortable/filterable table or raw JSON. Export JSON or CSV as appropriate.
10. Use **Change Plans**, **Activity Log**, **Sources** and **Diagnostics** to inspect approvals, execution history, provenance and runtime/compatibility health.

## Local Windows launch

Prerequisites:

- PowerShell 7 (`pwsh`)
- Python 3.13 available as `python` (or pass `-PythonPath` explicitly)
- Node 22.12 or newer in major 22, and npm 10 or 11 (tested with Node 22.22.0)

From the repository root:

```powershell
.\studio\scripts\start-studio.ps1
```

Useful flags:

```powershell
# Do not open the browser automatically
.\studio\scripts\start-studio.ps1 -NoBrowser

# Skip installation only after the launcher has verified current locked dependencies
.\studio\scripts\start-studio.ps1 -SkipInstall
```

Keep the launcher running. It starts hidden owned children, waits for both API
and authenticated proxy readiness, and opens `http://127.0.0.1:5173` unless
`-NoBrowser` is used. Ctrl+C or startup failure stops only its children. `-SmokeTest`
checks startup and then stops both children; `-CheckOnly` validates installation.
`-ApiPort` and `-UiPort` choose alternative loopback ports. Logs are in `studio/.run`.

The supported installation is repository-based and editable. Provider subpackages
and JSON manifests are packaged, but standalone wheels are not a supported runtime:
source discovery and upstream providers require the Toolbox checkout. `vite preview`
and opening `dist/index.html` are not supported authenticated launch topologies.

For repeatable developer checks, from repository root:

```powershell
python -m venv studio/backend/.venv
& ./studio/backend/.venv/Scripts/python.exe -m pip install -r studio/backend/requirements.lock
& ./studio/backend/.venv/Scripts/python.exe -m pip install --no-deps --no-build-isolation -e studio/backend
& ./studio/backend/.venv/Scripts/python.exe -m pytest -q studio/backend/tests
& ./studio/backend/.venv/Scripts/python.exe -m compileall -q studio/backend/app studio/scripts
Set-Location studio
npm ci
npm run test -w frontend -- --run
npm run build
npx -w frontend playwright install chromium
npm run test:e2e -w frontend
```

The browser fixture uses harmless provider responses behind the actual local
boundary, including the candidate broker. No tenant account is needed. It is a
separate test script, never a production environment bypass. CI runs these lanes
on Linux and Windows; remote CI evidence is separate from local checks.

CSV exports quote fields and prefix formula-leading cells (`=`, `+`, `-`, `@`, tab,
carriage return) with an apostrophe. CSV reflects visible rows/columns; JSON retains
the original displayed result including its invocation envelope. Filenames are
restricted to letters, numbers, periods, underscores and hyphens.

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

Integration branch: `fabric-ops-studio-v1`; S01 candidate: `codex/s01-reliability-foundation`.
