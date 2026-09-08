# Initial tech-lead audit — 2026-09-08

Verdict: **S01 reliability work approved; existing execution logic not accepted.**
This task created planning/coordination documents, not product fixes. The developer
must execute S01 before feature expansion. The next feature remains Security Audit.

## Evidence and limits

Inspected source: `af1c13e56f6c4cbe24d469679e93068c891e6dbe`, branch
`fabric-ops-studio-v1`, plus the existing untracked review dated today. Source
inspection covered Studio catalog, provider adapters, broker/models, API/activity,
diagnostics, UI workbench/context/client, launcher/manifests/CI, and immediate
upstream session/workspace/logging interfaces. This is not an audit of every
independent Toolbox tool or every one of the 479 discovered capabilities.

Executed in this session:

- `studio/backend/.venv/Scripts/python.exe -m pytest -q` from `studio/backend`:
  **27 passed in 26.22 seconds**.
- Isolated Python probes with `unittest.mock.patch`, synthetic tenant/parameters,
  fresh in-memory brokers and fake provider results; no Fabric/PowerShell dispatch
  and no real activity append. Results below.
- Catalog/diagnostics inspection: 479 entries; 168 read, two guarded-write,
  309 blocked; compatibility `incompatible`, six errors.
- Git branch/status/diff inventory, no network fetch or branch mutation.

Not run here: frontend build/browser, launcher startup, live authentication,
tenant reads/writes, packaging install or real subprocess timeout repro. The older
review reports other checks, including a frontend build; those remain historical
evidence and are not claimed as checks executed in this task.

## Findings

| ID | Priority | Evidence and consequence | Sprint response |
|---|---|---|---|
| F01 | P0 | `catalog.py:29` defaults unrecognized verbs to read; Capability defaults read risk to read execution. Actual admitted commands include Publish/Approve/Revoke/Move/Restore. `Publish-FabricEnvironment.ps1:52` sends POST; `Revoke-FabricCapacityTenantSettingOverrides.ps1:49` sends DELETE. Both can enter the generic read path under current policy. | REL-001 first; explicit reviewed admission, unknown blocked |
| F02 | P0 | `microsoftfabricmgmt.py:168` returns failure dict unchanged. `mutations.py:138` marks any returned validation validated, and `:166` marks apply/read-back executed without outcome comparison. Mock false results reproduced both. `_verify` returns any payload without expected-state check. | REL-002 / REL-012 |
| F03 | P0 | `mutations.py:126` returns live mutable plans. Digest calculated only on create. Editing returned parameters after failed validation changed stored plan and apply accepted it. Status check/transition is outside atomic claim. Concurrent duplicate dispatch is a risk from code inspection, not yet a threaded reproduction here. | REL-003 |
| F04 | P0 | `_same_session` compares tenant only; runtime flags have no generation. Upstream `powershell_session.py:237` auto-restarts. At `:190` blocking readline can outlast the checked deadline. Session/reconnect/timeout concerns require real fixture tests; no live failure was induced. | REL-004 / REL-012 |
| F05 | P1 | `diagnostics.py:54` expects `/v1/`; registered executor format is `GET /v1/`. Baseline has six errors; test permits either compatible or incompatible. Catalog dictionary merge can hide duplicate IDs before diagnostics. | REL-006 |
| F06 | P1 | `microsoftfabricmgmt.py:47` checks unknown names but not complete parameter schema; treats every bool as switch, omitting false. Regex discovery does not fully model parameter sets. | REL-005 |
| F07 | P1 | `activity.py:16` only redacts by key; synthetic token survived rendered command. `:42` reads whole file. API appends outcomes after successful calls, losing early failures. No app-level credential boundary exists. No remote exploit asserted. | REL-007 / REL-008 |
| F08 | P1 | Discovered create parameters include CapacityId; broker accepts and renders it even though README says capacity assignment remains blocked. Mock plan creation confirmed acceptance. | REL-001 restricts create parameters |
| F09 | P1 | No committed Studio lockfile; frontend tests absent; CI only filters Studio paths and integration-branch pushes. Launcher lacks complete native exit handling/readiness checks. Backend explicitly packages only app and runtime needs repo paths. | REL-009 / REL-011 |
| F10 | P1 | Workbench async completions unconditionally restore response state; reset effect keys capability/defaults rather than session generation. Client lacks abort/timeouts; failed apply UI can retain old plan state. Browser impact not yet reproduced here. | REL-010 |

Workspace cmdlets catch errors and call `Write-FabricLog -Level Error`; that helper
delegates to `Write-PSFMessage`. Do not assume `$ErrorActionPreference='Stop'` alone
makes every caught/logged error an upstream failure envelope. P1 must verify this
contract with harmless stubbed upstream command execution. Similarly, WhatIf is
a dry-run signal, not proof of eventual API authorization or apply success.

## Exact isolated probe output

```text
catalog {"total": 479, "policies": {"blocked": 309, "read": 168, "guarded-write": 2}}
compatibility {"status": "incompatible", "errors": 6}
read_verbs {"Get": 140, "Import": 1, "Publish": 1, "Approve": 1, "Revoke": 2, "Move": 1, "Connect": 2, "Initialize": 1, "Save": 1, "Write": 1, "Disable": 1, "Enable": 1, "Clear": 1, "Convert": 2, "Resolve": 5, "Restore": 1}
failed_validation_status validated
returned_plan_mutates_store ChangedAfterApproval
failed_apply_status executed
capacity_parameter_accepted True
command_secret_survives_redaction True
runtime_returns_failure_as_value True
```

The verb counts describe policy classification, not a claim that every non-Get
command mutates remote state. F01 is substantiated by the concrete POST/DELETE
source examples. The live mutable-plan probe demonstrates an internal integrity
defect; it is not a demonstrated HTTP parameter-edit exploit.

## Lead judgment

Repair the boundary before adding execution surfaces. Four substantial passes
are justified because policy/provider contracts, session/mutations, local audit
boundary and frontend/setup form one end-to-end operator workflow. The medium
developer runs regressions throughout; light performs independent integrated QA;
lead personally audits critical logic before deciding S02. No code acceptance
or deployment readiness is implied by the passing legacy suite.
