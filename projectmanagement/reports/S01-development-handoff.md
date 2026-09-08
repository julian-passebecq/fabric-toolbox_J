# S01 development handoff — 2026-09-08

## Verdict and next action

**NEEDS_TECH_LEAD.** Implementation has progressed through all four approved
passes, including independent installation/UI/CI work. The sprint is not complete,
accepted or ready for integrated light QA: production workspace writes are
suspended for a reproduced upstream contract defect.

Next owner: tech lead. Read `projectmanagement/prompts/TECH_LEAD_REVIEW.md`, this
report, and `studio/backend/tests/test_upstream_blockers.py`. Decide whether to:

1. Authorize a narrowly scoped upstream repair providing an explicit per-invocation
   no-retry contract for the two workspace writes, successful empty HTTP 204 handling,
   and error evidence distinguishing definite rejection from uncertain dispatch; or
2. Revise S01 acceptance to keep workspace writes deferred and review the read-only
   reliability candidate before admitting writes in a later approved pass.

Do not lift `WRITE_ADMISSION_SUSPENDED` just to make the original acceptance rows
appear green. Do not use negative retry counts or change PSFramework validation
as an undocumented workaround. No upstream implementation was modified.

The escalation follows OPERATING_MODEL's hidden-provider-behavior rule and S01's
instruction to keep a write blocked if it cannot meet its contract. This is a
concrete provider finding, not a request to approve routine development.

## Source identity

- Branch: `codex/s01-reliability-foundation`.
- Verified integration base: `af1c13e56f6c4cbe24d469679e93068c891e6dbe`.
- Code candidate: `79aedecccb5edcffb2b139aea61038e4b4c719d6`.
- Diff: base through candidate. Subsequent commits contain planning/evidence only.
- Existing root `AGENTS.md` and `studio/docs/REVIEW_AND_ACTION_PLAN_2026-09-08.md`
  remain untracked and preserved. Existing installation metadata/build/cache paths
  remain on disk under new narrow ignore rules. No generated bundles or credentials
  entered the code commit. Planning baseline files are deliberately retained with
  the final handoff records.
- Windows 11, Python 3.13.1, Node 22.22.0, npm 10.9.4 for clean installation;
  npm 11.19.1 was used to resolve patched Vitest after an npm 10 resolver defect.
- No push, merge, deployment, model-role handoff, or real tenant operation occurred.

## Outcome

P1: Discovery defaults to blocked execution. Four reviewed PowerShell inventory
reads and six registered REST GETs are admitted by fingerprint. Create no longer
accepts CapacityId. Shared typed validation, exclusivity, quoting, REST declarations,
duplicate detection and versioned invocation outcomes are implemented. The REST
builder now enters the actual module auth context; baseline Get-FabricAPIHeaders
was not present in this upstream source. Actual API-helper array output is preserved.

P2: Session generation and dispatch checks cover queued operations, reconnect and
process loss. Immutable canonical snapshots bind commands, source/loaded artifact,
parameters, tenant/generation, verification, ID and expiry. Claims are atomic, DTOs
detached, and terminal results cannot be replayed. Candidate create/update verification
compares unique identity and requested fields. Writes remain blocked in production.

P3: Both listeners enforce the local Host/Origin boundary. Vite injects the per-launch
credential server-side. Structured bounded activity omits arbitrary commands,
parameters/results/errors and sanitizes legacy history. Audit-start failure prevents
mutation dispatch; outcome failure retains the result with a warning.

P4: Locked dependency installation, provider package discovery, 0.8.0 version
alignment, hidden owned-process launcher readiness/cleanup, stale SkipInstall
checks, context-safe UI, component/browser tests, and provider-aware Windows/Linux
CI lanes are present. Documentation describes current suspension and limits.

## Acceptance evidence

See [S01-validation.md](S01-validation.md) for exact commands, durations, evidence
categories and acceptance mapping. Candidate broker/UI write tests explicitly use
mock/no-network fixtures with test-only admission. They do not prove that real
workspace writes satisfy the upstream contract. Production suspension is separately
tested and has no configuration/environment override.

Live L01/L02: **NOT RUN**. Remote GitHub CI: **NOT RUN**. Lead acceptance and
independent light QA: **NOT RUN**.

## Findings / repairs

| ID | Severity | Reproduced behavior / action | State |
|---|---|---|---|
| S01-F01 | P0 | Upstream POST 503/504 with MaxRetries=0 invokes the request four times. Workspace cmdlets do not pass a no-retry control. | Writes blocked; lead decision |
| S01-F02 | P0 | Upstream HTTP 204 throws, including a successful empty update; generic caught error also loses evidence needed for definite-vs-uncertain outcome. | Writes blocked; lead decision |
| S01-F07 | P1 | Hidden Windows PowerShell defaults replaced Unicode with question marks. | UTF-8 output, ASCII-safe Unicode commands, and real-session regression |
| S01-F03 | P1 | Upstream startup enters an interactive REPL and stalls on compound commands. | Narrow Studio startup/termination extension; real persistent fixture passes |
| S01-F04 | P1 | REST renderer referenced nonexistent Get-FabricAPIHeaders and API helper returns a nested pipeline array. | Module-scoped auth/read wrapper and normalization fixture |
| S01-F05 | P1 | Selected operation retained offline metadata when the live catalog arrived. | Refresh selected metadata and reset form/request identity; component/browser regression |
| S01-F06 | P1 | npm 10 peer resolver fails on patched Vitest. | Resolve with npm 11, then verify npm ci with npm 10 and locked dependencies; audit clean |

The no-network upstream reproducer asserts four invocations for 503/504 and one
invocation plus failure for 204. These assertions document the defect; they are not
passing production write acceptance.

## Logic and decisions for lead attention

- `admission.py`, `admission.json`, `provider_sources.json`: source/contract admission
  and unconditional production write suspension. Line endings are normalized for Git.
- `providers/outcomes.py`: owned versioned envelope; caught/terminating errors,
  literal domain error fields, WhatIf host prefix, and unary-comma array handling.
  The unresolved write-failure interpretation must be revisited with upstream status
  evidence before admission is restored.
- `session_extension.py`: retains upstream run/sentinel methods; explicitly starts
  stdin command mode, terminates compound input and bounds blocking reads by killing
  the owned process and joining workers. Implicit restarts are prohibited.
- Lock order: session I/O -> short broker callback -> session-state lock. Broker
  claims release the bookkeeping lock before requesting session I/O. List/get do not
  acquire the I/O lock. Dispatch callbacks recheck snapshot/generation/expiry.
- `artifact_identity.py`: compares loaded function AST bodies with repository sources
  and binds source/module-file/transport hashes. It does not claim a signed binary
  or portable wheel. A stale built module blocks dispatch rather than trusting a
  source-file hash alone.
- `mutations.py`: validation and apply attempts own completion; post-dispatch timeout
  is unknown, successful apply with failed read-back is applied_unverified. All are
  terminal. Expiry only blocks new dispatch.
- `boundary.py`, Vite config, `activity.py`, `launcher.py`: review these together as
  the per-launch shared-runtime client boundary and audit lifecycle.
- UI context: tenant draft is separate from connection; session/workspace/item keys
  remount operation state, request scopes discard delayed responses, reads abort.
  A lost apply HTTP response terminalizes the UI as unknown, without retrying.

## Effort and continuation

One developer assignment progressed P1 through P4 without pass-by-pass user
interventions or delegation. Rough effort estimates (not stopwatch measurements): P1 about 15 minutes, P2 about
20 minutes, P3 about 10 minutes, P4/integration about 35 minutes, plus installation
waits. Most effort went to provider fixtures, state/dispatch integration, dependency
installation and browser checks. The only required role
stop is the upstream architecture decision. A long temporary checkout path hit
Windows MAX_PATH; a short isolated checkout was used instead without changing
user-wide Git settings. No unattended work is claimed after this handoff.

After the lead records its decision, the developer should resume the affected
write contract, update reviewed manifests only after source review, rerun the
integrated matrix, and then hand off once to independent light QA. Do not begin S02.
