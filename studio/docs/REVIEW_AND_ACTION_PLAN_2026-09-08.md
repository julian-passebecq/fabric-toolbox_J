# Studio review and action plan — 2026-09-08

## Scope and baseline

Reviewed Fabric Ops Studio on `fabric-ops-studio-v1`, commit `af1c13e56f6c4cbe24d469679e93068c891e6dbe`. Fetched the branch from origin; it matches the ZIP's expected commit. The original clean checkout was on `main`. The ZIP contains continuity documents, not source code. Its proposed Security Audit work is background context, not an instruction to implement it during this review.

This assessment covers Studio and its immediate provider interfaces, not every independent upstream Toolbox sample. No Fabric login, tenant reads, remote mutations, publishing, or deployment were performed. Application source has not been changed.

## Architecture understood

React 19, TypeScript, Vite and Fluent UI provide the operator console. FastAPI discovers upstream PowerShell capabilities, overlays curated metadata, exposes registered Fabric REST reads, and delegates execution through the upstream persistent PowerShell session. A mutation broker permits only workspace create/update. Security Audit, Assessment and Lineage are catalog or handoff surfaces.

The discovered catalog contains 479 entries: 471 MicrosoftFabricMgmt, seven REST and one Security Audit; 168 read, two guarded-write and 309 blocked policies. Studio should retain ownership of orchestration, context, validation and presentation while upstream tools retain domain implementations.

## Validation evidence

- Created an isolated backend `.venv`; editable install plus pytest/httpx succeeded using Python 3.13.1.
- Existing backend suite: **27 passed in 44.81 seconds**.
- Python application compilation: passed.
- FastAPI TestClient smoke checks: health, capabilities, sources, tools and diagnostics returned HTTP 200. Disconnected read execution returned HTTP 409.
- PowerShell launcher syntax: zero parse errors. Actual launcher/process readiness and tenant authentication were not tested.
- `npm ci` failed because Studio has no committed lockfile. Fallback `npm install --package-lock=false` installed 158 packages and reported zero vulnerabilities at install time; this is not a comprehensive security audit.
- System Node 21.7.1 is outside the installed Vite/plugin engine ranges. TypeScript and the Vite production build passed using bundled Node 24.19.0 (2,160 modules transformed; Vite build 26.98 seconds).
- Additional isolated mock probes reproduced the mutation and redaction findings below. They did not execute PowerShell or write real activity records.
- No browser interaction or authenticated end-to-end test was performed. A production build is not a substitute for those tests.

## Findings and implementation order

### 1. P0 — Make provider failures fail the operation

**Evidence:** `app/providers/microsoftfabricmgmt.py:run_json` returns parsed failure dictionaries unchanged. `app/mutations.py:validate` sets `validated` after any returned value; `execute` sets `executed` after any returned value. A fake provider returning `{"success": false}` reproduced both incorrect terminal outcomes. The upstream session explicitly returns structured JSON on PowerShell errors, so this is relevant to the actual transport contract.

**Actions:** Normalize provider outcomes and errors at the adapter boundary; reject unsuccessful validation; distinguish an unsuccessful apply from successful apply followed by failed verification. Verify expected workspace state instead of treating any read-back payload as confirmation. Preserve upstream error context without disclosing secrets.

**Acceptance:** Failed WhatIf cannot authorize apply; provider failure cannot become executed; read-back mismatch is visible; tests exercise structured failures, exceptions, empty output and ambiguous post-write results.

### 2. P0 — Enforce plan integrity and atomic lifecycle

**Evidence:** The broker calculates a SHA-256 digest only at plan creation; it does not recompute it before execution. Plans are mutable objects returned by `get`/`list`. A mock probe changed stored parameters after validation and execution accepted them with the original digest. This is an internal integrity reproduction, not a demonstrated HTTP parameter-edit exploit. Lifecycle checks and transitions run outside the broker lock; concurrent validate/apply and session changes need dedicated tests.

**Actions:** Store immutable snapshots, verify canonical parameters and exact command against the approval digest, and atomically claim a plan before work. Coordinate tenant/session generation with command dispatch, including reconnects and PowerShell restarts. Avoid holding a global bookkeeping lock across slow I/O; use explicit per-plan/session coordination.

**Acceptance:** Tampered parameters/command/catalog semantics are rejected; concurrent callers dispatch at most one apply; late validation cannot reopen an executing plan; expiry and session changes invalidate approval; running plans cannot expire into misleading states.

### 3. P1 — Repair diagnostics and make CI detect the real contract

**Evidence:** Diagnostics returns `incompatible` with six errors. `_compatibility_report` expects endpoints to start with `/v1/`; the REST executor expects `GET /v1/...`. Existing tests assert report shape and permit either compatible or incompatible, so they miss the false alarms.

**Actions:** Share endpoint declaration parsing between diagnostics and execution; assert the actual baseline catalog is compatible. Add HTTP route tests and provider error-contract tests. Trigger Studio CI when its upstream PowerShell sources, session adapter, or specialized entrypoints change; current workflow filters only Studio and its workflow file.

**Acceptance:** Current registered GET endpoints pass; malformed endpoints and unsupported methods fail; relevant upstream-only changes trigger CI; failure probes from this review become regression tests.

### 4. P1 — Improve validation, audit accuracy and local session boundary

**Evidence:** PowerShell invocation checks unknown names but does not enforce discovered mandatory values/types/allowed values. Activity redaction uses dictionary-key matching: a synthetic token was masked under `parameters.token` but retained inside `rendered_command`. Exceptions raised before append in API routes are not recorded as failed attempts. Activity reads load the entire growing file. API routes use a shared runtime and have no application-level client authentication.

**Actions:** Validate PowerShell parameters against their metadata, including boolean versus switch semantics. Create redacted command displays from structured inputs and scrub free-text outputs/errors; add retention and bounded history reads. Log start/outcome with run IDs and duration, including failures. Define and test the intended localhost client boundary (host/origin validation and an appropriate per-launch client token), while preserving the local operator experience.

**Acceptance:** Invalid forms are rejected before invoking PowerShell; synthetic secrets never enter exported history; failure attempts are traceable; history remains bounded; untrusted client requests cannot use an authenticated backend session. Treat the API boundary as hardening work, not a proven remote exploit.

### 5. P1 — Make fresh setup repeatable

**Evidence:** No Studio lockfile; local Node engine mismatch; launcher checks command availability rather than version and does not explicitly fail on each native install exit code. It reuses `node_modules` solely based on directory existence. Backend packaging explicitly includes only `app`, so a distributable wheel needs checking for `app.providers`. Reported versions differ: handoff milestone 0.7, API 0.5, package metadata 0.1.

**Actions:** Commit the frontend lockfile and use npm ci in CI; declare supported runtimes; establish reproducible backend dependency constraints. Add launcher version/import checks, native exit-code handling, dependency freshness checks, port collision detection and readiness polling. Verify wheel contents/install in a clean environment or explicitly document editable repository-only support. Align version metadata.

**Acceptance:** A fresh supported Windows environment installs and builds predictably; unsupported runtimes and failed installs stop with actionable messages; launch verifies both services; packaging behavior is tested.

### 6. P1 — Add frontend behavioral coverage

**Evidence:** Studio frontend has build/dev scripts but no automated behavior-test script. Tenant/workspace/item inheritance and guarded confirmation depend on React state and are not exercised by the Python suite.

**Actions:** Add focused component tests and a small browser smoke suite for context resets, stale response handling, offline catalog indication, parameter inheritance, failed validation, double-submit prevention, expiry and result exports. Check keyboard operation and accessible error/status announcements. Add request cancellation/timeouts where slow work would otherwise leave stale results.

**Acceptance:** Tenant/workspace switching cannot retain obsolete item results or reusable approval UI; failure and loading states are usable; export and navigation flows pass in a browser.

### 7. P2 — Deliver Security Audit as the next feature

After execution safeguards and baseline tests are repaired, implement a specialized adapter around `tools/fabric-security-audit/Invoke-FabricSecurityAudit.ps1` without copying its collection logic.

Split into two reviewable deliveries:

1. Readiness and preview: inspect actual upstream NoPrompt/authentication behavior; validate URL or workspace/item targets; allowlist parameters; preserve safeguards; constrain output paths; present exact invocation and prerequisites.
2. Managed runs and artifacts: bounded subprocess lifecycle, status/error capture, cancellation, run history, read-only Markdown/JSON/CSV preview and original ZIP download. Prevent path traversal, unsafe report rendering and unbounded artifact loading.

**Acceptance:** Stubbed success/failure/cancellation and hostile path/content tests pass; a Windows operator can preview and run an audit and inspect its original bundle. Separately record authenticated test results in a designated test tenant when such a session is available.

### 8. P3 — Expand useful operations after the first vertical slice

Add item/run drill-down, compatibility baseline diffs and monitoring entry points; then Assessment orchestration around the existing tool. Evaluate any further writes individually with tested idempotency, confirmation, verification and blast radius. Keep analytical authoring outside the product scope.

## Suggested work batches

1. Provider outcomes and mutation integrity, with regression tests.
2. Diagnostics, validation, audit records and session boundary.
3. Dependency/launcher/CI reliability and frontend behavior tests.
4. Security Audit preview, then managed execution and results.
5. Operator drill-down and additional specialized tools.

Each batch should be independently reviewable and run backend tests, compilation, frontend build and launcher checks as relevant. Update changelog/roadmap only after behavior is implemented. Do not use the passing legacy suite or the handoff's historical CI success as evidence that live tenant behavior is correct.
