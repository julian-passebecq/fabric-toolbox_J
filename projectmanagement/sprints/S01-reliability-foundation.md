# S01 — Trustworthy execution from a repeatable local installation

Status: APPROVED_FOR_DEV. Owner: medium development model. Independent verification:
light test model. Acceptance: tech lead. Baseline: `af1c13e5` on
`fabric-ops-studio-v1`. Read DECISIONS and TEST_STRATEGY before coding.

## Outcome and scope

A supported local installation can inspect registered operations and handle the
two narrowly scoped workspace writes without silently bypassing policy, confusing
failure with success, mixing tenant contexts, replaying an apply, or leaking
secrets into activity history. Offline tests demonstrate the required properties.

All four passes are approved as one assignment. Finish a pass, update the compact
checkpoint, and continue to the next. Do not request light QA at every milestone.
This is deliberately a substantial integration sprint; the lead may split it only
if evidence shows an architectural dependency that cannot be resolved within scope.

Allowed areas: `studio/**`, Studio CI, narrowly scoped ignore rules, and project
management records. Upstream source is reference material; a necessary upstream
logic/transport modification requires the specific lead review described in D01/P2.
No new executable writes, specialized runners, UI redesign, deployment, or broad
dependency upgrade campaign. Do not execute the known-unsafe baseline against Fabric.

## P1 — Execution policy, input contracts, and provider outcomes

Backlog: REL-001, REL-002, REL-005, REL-006. This pass ends with a trustworthy
admission/validation/provider boundary and regression fixtures, not just renamed errors.

1. First reproduce baseline policy defects locally. Explicitly block mutations
   misclassified as reads, including Publish, Approve, Revoke, Move, Restore,
   Enable/Disable, Import, and session/utility operations pending inspection.
   Replace default-read admission with D02/D03. Review the source of reads needed
   for existing UI journeys; record their contracts and provenance. Unreviewed
   commands remain visible with a blocked reason. Do not bulk bless all Get verbs.
2. Remove `CapacityId` from the permitted workspace-create parameter surface in
   backend policy and frontend form. Retain WorkspaceName/WorkspaceDescription.
   Validate update's required-any-of condition. Preserve unrelated upstream parameters
   in catalog reference metadata where useful, but distinguish them from allowed input.
3. Introduce shared parameter validation/rendering inputs. Handle strings, GUIDs,
   integers, booleans, switches, arrays, ValidateSet, mandatory values, null/blank,
   non-finite numbers and unknown names. Inspect parameter-set/exclusivity semantics
   for admitted commands, particularly Get-FabricWorkspace's ID versus name.
   Unsupported shapes yield explicit pre-dispatch rejection. Do not turn arbitrary
   object/string coercion into PowerShell code. Preview and execute use the same rules.
4. Normalize invocation outcomes and errors at the adapter, including documented
   upstream `{success:false,error,error_type}`, exceptions, invalid/mixed output,
   and no output. Test actual upstream workspace catch/log behavior and WhatIf
   stream capture with stubbed dependencies: the wrapper currently hardcodes success.
   Preserve valid data objects/arrays; use a versioned envelope to disambiguate data
   from control. Add explicit per-operation empty-response semantics.
5. Share REST method/path parser between diagnostics and execution; enforce read
   policy at the REST builder too. Validate registered methods/placeholders and
   parameter declarations; baseline admitted endpoints must report compatible.
   Detect duplicate raw entries before catalog merging silently overwrites them.

Milestone M1: TEST_STRATEGY C01-C07 and O01-O04 pass; all baseline unsafe reads
are blocked; inventory/registered REST fixtures remain usable. Provider outcomes
are available for P2. Update changed API types minimally so the frontend builds.

## P2 — Session coordination and mutation lifecycle

Backlog: REL-003, REL-004, REL-012. Implement the full failure/state/dispatch path.

1. Add session generation and lifecycle coordination around connect, read,
   validate, apply, close and subprocess loss/restart. Failed connect clears stale
   identity. Check the expected generation at dispatch, including queued reads.
   Prevent upstream auto-restart from silently running a command as an authenticated
   old session. Prove no-output timeout behavior and process/worker cleanup with a
   harmless subprocess. Use DECISIONS' escalation if the upstream contract cannot
   support a safe narrow wrapper.
2. Keep immutable internal plan snapshots, detached response models, canonical
   digests, and full semantic fingerprints. Recompute/recheck on validation and
   execution, including the provider/source actually loaded, not only displayed
   source. Do not claim a source-file hash verifies a stale built module; establish
   and record the loaded artifact identity, or block guarded writes on mismatch.
3. Implement the state table and atomic claims. Use fake clock and deterministic
   barriers in tests, not sleep-based races. No lock across slow I/O that blocks
   list/get/history; no late validation can reopen an executing/terminal plan.
   One dispatch at most per plan. Exceptions and expired dispatch queues terminate
   truthfully; session coordination has a documented lock order.
4. Verify create via returned workspace identity and update via requested ID/fields.
   Do not accept the first name match as proof of creating a new workspace.
   Bounded read-back attempts may accommodate eventual consistency; retries of
   read-back are distinct from retrying apply. Empty update output can be valid;
   empty/mixed/failed apply evidence must never be silently marked executed.
5. Distinguish validation failure, definitive apply failure, uncertain apply,
   successful apply/unverified result, and fully verified execution. Bring these
   states through HTTP DTOs, workbench, Change Plans, and historical rendering.

Milestone M2: O05-O07 and M01-M10 pass. The developer writes a short explanation
of the lock order, generation check location, and unknown-outcome handling for
the eventual lead review. Continue to P3 unless a genuine architecture escalation
is needed; M2 is not a routine user stop.

## P3 — Local boundary and truthful durable activity

Backlog: REL-007, REL-008. Integrate with the actual launcher/proxy.

1. Implement D09's credential/host/origin flow, loopback listeners, protected API
   routes, and secure proxy forwarding. Keep credentials out of UI state, logs,
   URLs and built bundles. Verify direct API requests and frontend-proxy requests.
   A manually started backend without configured credentials must fail closed
   with an actionable setup error rather than silently allowing shared-session access.
2. Add run/attempt IDs, start/end/duration/outcome records for reads, connection,
   validation and mutation, including errors before previous append calls. Use
   structured redacted summaries and safe command displays; do not persist arbitrary
   result text by default. Scrub known sensitive values from allowed text fields;
   avoid pretending a generic regex proves all arbitrary text safe.
3. Bound record bytes, retention/rotation and paginated or tail-based reads.
   Define documented defaults (suggestion: 256 KiB record limit, 10 MiB files,
   five rotated files, 1,000 records maximum per response) and test the chosen
   constants. Handle malformed/truncated records and disk-write failures without
   crashing history or misrepresenting/replaying an apply. Preserve old history
   compatibility while never restoring approvals.

Milestone M3: A01-A07 pass; app can still connect through the supported local
proxy flow using test stubs; no synthetic secret appears in stored/exported history.

## P4 — Repeatable setup, frontend behavior, CI and handoff

Backlog: REL-009, REL-010, REL-011. Integrate, repair, and make the result testable.

1. Commit the npm workspace lockfile; use `npm ci`. Select one supported Node LTS
   major whose installed engine ranges pass; declare it in package metadata/docs/CI.
   Pin/lock backend runtime and test dependency resolution through a documented
   reproducible mechanism. Correct package discovery for providers; document
   repository-only editable runtime support and align the current release version.
2. Launcher checks actual runtime versions/imports, native exit codes, dependency
   freshness, both port collisions, service readiness and ownership-aware shutdown.
   Startup failure cleans up only processes it created. Provide unattended test
   mode/hidden windows and useful logs. Verify SkipInstall accurately. No fixed
   two-second assumption. Narrow ignore rules cover generated Studio outputs.
3. Add frontend behavior runner (Vitest + React Testing Library is the intended
   fit) and a small Playwright browser suite using deterministic mock endpoints.
   Select compatible versions and lock them. Test real UI actions, HTTP state and
   DOM assertions; no giant snapshot suite. Do not require a Fabric account in CI.
4. Separate connected tenant/generation from editable tenant input; clear obsolete
   workspace/item/plan/results on context changes, reconnect and failed reconnect.
   Ignore late responses using request/context identity; add AbortController for
   reads. Handle unknown write outcomes without retry buttons that re-dispatch.
   Ensure typed confirmation, expiry, disabled actions, errors, exports, keyboard
   use and status announcements work in workbench and relevant pages.
5. Update CI filters for Studio and immediate provider/module/registry/specialized
   dependencies. Cover push to the sprint branch or all `codex/**` branches with
   relevant paths, plus PRs. Run backend contract/route tests, compilation, frontend
   tests/build, browser smoke and Windows launcher checks. Provide stable documented
   commands; do not treat a workflow YAML edit as evidence it ran on GitHub.
6. Update user docs/changelog to actual behavior; reconcile outdated safety claims
   and roadmap checkboxes. Write the developer report and final acceptance mapping,
   update STATUS and backlog to READY_FOR_LIGHT_QA, and identify the exact candidate.

Milestone M4: U01-U07 and E01-E06 pass. All prior milestone checks pass on the
integrated candidate. Report external/environment skips explicitly. Hand off once.

## Sprint acceptance

All required S01 offline rows pass on the reviewed candidate; no unresolved P0/P1
local defect; lead audits policy, upstream outcome behavior, session/locking,
verification, local boundary and UI context. Live validation may be NOT RUN with
an explicit acceptance limit; do not call the result tenant-validated or production
ready. If an admitted write cannot meet its contract, keep it blocked and ask the
lead to decide scope/acceptance rather than weaken the contract.
