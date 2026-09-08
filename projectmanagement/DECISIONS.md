# Architecture decision register

Status: approved direction for S01, 2026-09-08. Implementation is still pending.
The medium model may choose internal names and small module boundaries while
preserving these semantics. Record a concrete alternative and consult the lead
if the contracts cannot be satisfied.

| ID | Decision | Reason / consequence |
|---|---|---|
| D01 | Keep the current local React/FastAPI architecture and upstream domain implementations | Repairs should strengthen existing boundaries; no product rewrite |
| D02 | Separate discovery from executable admission | Unknown verbs currently become read, including actual POST/DELETE commands; a larger verb denylist alone is insufficient |
| D03 | Admit an explicit reviewed subset of reads, with source/contract fingerprint and rationale; drift blocks execution pending review | Keep broad catalog visibility while preventing upstream additions/changes silently acquiring permissions; prioritize existing UI journeys, defer obscure commands |
| D04 | Normalize a versioned invocation envelope at the provider boundary | PowerShell failure JSON and business payload must not be confused; no arbitrary string/empty result treated as proof of successful validation |
| D05 | Bind tenant, session generation, commands, parameters, verification and catalog identity into immutable approval snapshots | Same tenant after reconnect is a different session; mutable DTOs and digest presence do not enforce integrity |
| D06 | Atomic per-plan claims plus coordinated session dispatch; one local API worker | Prevent duplicate application and cross-tenant dispatch without locking list/history over remote I/O; multi-worker deployment unsupported |
| D07 | Separate apply outcome from verification and never retry an uncertain write automatically | Read-back failure cannot truthfully mean the write failed; a timeout can occur after a real mutation |
| D08 | Exclude CapacityId from workspace-create admission in S01 | Capacity assignment has not had its own semantics/blast-radius review |
| D09 | Protect direct API access with per-launch client credential and host/origin checks; Vite development proxy injects credential server-side | Avoid adding a login screen to a local app or embedding the credential in browser bundles |
| D10 | Persist bounded structured redacted activity summaries; approvals stay memory-only | Arbitrary result/error/command strings cannot be guaranteed safe by key matching; history is evidence, never executable state |
| D11 | Support repository-based editable backend installation for this sprint; include subpackages correctly but do not claim a portable standalone wheel | Runtime and source discovery require the Toolbox checkout; standalone distribution is a distinct future packaging decision |
| D12 | Add focused component and browser behavior tests in P4 | Python tests and TypeScript compilation cannot validate context race conditions or user interaction |

## Mutation lifecycle

Use an explicit state table in code and tests with these meanings:

| State | Allowed next step |
|---|---|
| planned | Atomically claim validation, or expire/invalidate |
| validating | Owning attempt finishes as validated or validation_failed; never dispatch apply here |
| validated | Atomically claim execution while snapshot/session/expiry still match; or expire/invalidate |
| executing | Owning attempt finishes as executed, applied_unverified, failed, or outcome_unknown |
| validation_failed | Terminal; new plan required |
| expired / invalidated | Terminal; no dispatch |
| executed | Apply succeeded and expected state verified; terminal |
| applied_unverified | Apply explicitly succeeded but read-back failed/mismatched/was ambiguous; terminal |
| failed | Definitive provider/apply failure, with stage and evidence; terminal |
| outcome_unknown | Dispatch may have reached Fabric; outcome cannot be determined; terminal and no replay |

Do not offer repeat validation of a validated plan in S01: create a new plan when
validation needs refreshing. This simplifies concurrency and makes failure semantics
clear. Existing UI and API types must change together. History must tolerate older
states and must not recreate a live plan from old events.

Track `attempt_id`, stage, apply outcome, verification outcome, and sanitized reason
separately from the label. For invalid requests rejected before dispatch, preserve
the plan if safe (for example wrong typed confirmation), record the attempt, and
do not claim a remote operation occurred. Never label a timed-out active apply expired.

## Runtime detail to resolve within P2

The upstream session auto-restarts and uses blocking stdout `readline()` inside a
deadline loop. A timer checked before a blocking read does not bound that read.
The developer must test actual no-output stalls with a harmless subprocess fixture.
Prefer a narrow Studio transport wrapper/extension retaining upstream domain code;
use a process lifecycle boundary that can terminate a hung owned process and join
its workers. A timeout around an abandoned thread is insufficient. If a supported
extension cannot reliably observe process generation or stop a hung dispatch,
bring that evidence and the smallest adapter/upstream change to the lead before
replacing the transport. Keep potentially unsafe operations blocked in the interim.

## Local development credential flow

Launcher generates a random credential per launch and supplies it to backend and
Vite's server process through environment variables. Vite's `/api` proxy strips
any client-supplied credential header and injects the server-side credential.
Backend checks it for all API routes except a minimal non-sensitive health route.
Both listeners remain loopback-only; the frontend server also validates its allowed
host and origin because it holds the credential. Reject foreign origins even if a
token is present. Allow requests without Origin only with a valid credential and
allowed Host (CLI and server proxy); CORS alone is not authorization.

Automated API fixtures inject a synthetic credential via test configuration,
never a global production auth bypass. Browser tests exercise the proxy as well
as direct API rejection. A production static-server topology is deferred; do not
claim `vite preview` or opening `dist/index.html` is the supported authenticated
launch. This boundary does not claim isolation from malware running as the same OS user.

## Audit failure behavior

For mutations, inability to persist the required start record rejects dispatch.
If outcome logging fails after dispatch, retain the in-memory terminal outcome,
return an explicit audit warning, and never replay the write. After a restart,
an unmatched durable start is shown as interrupted/unknown history. Use run IDs
and attempt IDs to correlate failures, including validation and rejected attempts.
Record rejected unauthenticated requests only as bounded sanitized metadata to
avoid turning malicious request bodies into log content.
