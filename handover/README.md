# Fabric Ops Studio: Pro AI takeover

Snapshot: 2026-09-11. Start from branch `codex/pro-ai-handover-2026-09-11`.

## Request and working agreement

The user is ending the expensive multi-agent workflow and wants one Pro AI to take over. This pass preserves work and explains outcomes and remaining requirements; it does not implement another sprint. Use this document first, consult the linked evidence as needed, and avoid rereading whole conversations or reproducing the planning system. Historical lead/developer/light roles explain provenance, not a requirement to launch more agents. The Pro AI owns implementation choices. S02 and later remain proposed scope, not silently approved development.

## Product and existing app

Build a local Windows Fabric operations console: connect, select tenant/workspace/item, inspect inventory and operational state, preview a registered action, confirm a permitted change, then inspect its result and history. Reuse Toolbox's established PowerShell/API/audit/assessment implementations; Studio owns orchestration and presentation. React/TypeScript/Fluent UI frontend, FastAPI backend, one coordinated local Fabric session. This is repository-based software, not a standalone installer or multi-user service.

The original request was to test and understand the existing v0.7 Studio and propose improvements. A subsequent request introduced architecture, backlog, staged development and independent QA. Reliability was prioritized because the baseline could report failed writes as success and did not adequately enforce approval integrity. S01 development completed four passes, reaching the 0.8.0 candidate, but the sprint is **not accepted**.

Existing surfaces include inventory, searchable capability/operation forms, workspace/item context, read execution, result export, change plans, activity history, diagnostics and specialized-tool discovery. The reviewed executable read subset covers workspaces, roles, capacities, connections and six REST GET registrations for item details/connections, runs, schedules and Git status. Catalog visibility is not authorization: most discovered operations are blocked. Specialized-tool discovery is not a completed managed runner.

## What changed and why

S01 added fail-closed capability/source admission and parameter contracts; normalized provider outcomes; immutable, single-use approvals with session binding; concurrency/expiry handling; distinct uncertain and unverified write outcomes; local client/Host/Origin protection; bounded redacted activity records; context-safe UI and stale-response handling; locked dependencies, launcher lifecycle checks, and component/browser/provider-aware CI coverage. Persistent PowerShell startup, timeout cleanup, REST result normalization and Unicode transport defects were repaired. These are developer-reported implementations backed by the recorded fixtures, not a new independent audit by this handover pass.

## What is broken or blocked

**All production writes remain disabled, including workspace create/update.** The original upstream API helper repeats POST requests four times on 503/504 even with `MaxRetries=0`, and throws after a successful empty HTTP 204. Its errors do not reliably distinguish definite rejection from uncertain dispatch. Passing tests that reproduce these bugs do not prove safe writes. No runtime configuration bypass exists or should be inferred.

The next product decision is whether to finish a reliable upstream write contract for the two workspace operations or explicitly deliver a read-only milestone. Completion requires honest outcomes, no unintended repeated writes, and trustworthy verification. Keep suspension until that contract is demonstrated. REL-002, REL-003 and REL-012 remain blocked; the other S01 development rows await review.

Independent QA, final logic acceptance and real tenant validation have not happened. No live authentication, inventory or mutations were tested. Historical remote CI was not run; consult the publication record for this push. A handover branch is not a production release.

## Remaining outcomes for the full app

| Priority / scope | Required outcome before calling it complete |
|---|---|
| Finish S01 | Resolve write scope; independently challenge execution, session/concurrency, approval and audit behavior; record acceptance against the actual candidate; obtain remote CI evidence and separately identified live evidence. |
| Security Audit (proposed S02) | Operator understands prerequisites and exact target/action; can start, observe and cancel a bounded audit; can inspect partial/final original reports and download the bundle. Authentication, failure and cleanup behavior must be clear. |
| Investigation (proposed S03) | Workspace/item/run navigation preserves correct context; useful operational summaries and monitoring entry points support investigation without repeated ID copying. |
| Compatibility (proposed S04) | Show added/removed/changed upstream capabilities, parameters and source semantics; expose update provenance without silently changing execution permissions. |
| Assessment (proposed S05) | Readiness, managed execution and original artifacts for the existing assessment tool, with its own dependency/authentication lifecycle. |
| Later scope decisions | Lineage notebook handoff; individually reviewed job, schedule, item, Git and deployment changes. Each needs clear confirmation, outcome, verification and failure behavior. Roles, capacity and destructive operations remain deferred. |
| Release readiness | A supported fresh Windows setup, usable errors/empty/loading states, tested exports/accessibility, accurate docs, and explicitly scoped tenant verification. Standalone distribution needs a separate product decision. |

These are desired outcomes, not coding instructions or promises that every proposed feature belongs in the next release. DAX, model/measure/report/visual authoring remain excluded. Detailed requirement IDs and status live in [BACKLOG.csv](../projectmanagement/BACKLOG.csv); product boundaries in [VISION_ARCHITECTURE.md](../projectmanagement/VISION_ARCHITECTURE.md).

## Read only what is needed

1. This document plus [publication and provenance](PUBLICATION.md) gives the takeover context.
2. For the immediate blocker and acceptance evidence: [S01 development handoff](../projectmanagement/reports/S01-development-handoff.md) and [validation map](../projectmanagement/reports/S01-validation.md).
3. For running the app: [Studio README](../studio/README.md). For a specific repair, inspect the relevant source/tests and requirement, not the whole repository.

Suggested message to the Pro AI: "Take over Fabric Ops Studio from codex/pro-ai-handover-2026-09-11. Read handover/README.md first. Explain the immediate scope decision and remaining release outcomes concisely, then work within the scope I approve. Use existing evidence, keep a resumable checkpoint, and do not recreate the multi-agent workflow."
