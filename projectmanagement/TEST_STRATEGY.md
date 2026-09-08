# Verification contract

Developer implements regression tests during each pass. Light independently runs
the integrated suite, challenges the fixtures and checks behavior through the API
and UI. Lead audits the code paths and whether the tests prove the contracts.

For every row below report PASS / FAIL / BLOCKED / NOT RUN, test path or manual
procedure, exact command, revision, duration, and evidence. PASS requires executed
assertions; test existence/build success is insufficient. Rows C through E are
required for S01; L rows are separate live-environment evidence. Tests need realistic
provider output captured from inspected upstream behavior or local stub invocations,
not just success dictionaries invented to satisfy implementation.

## Isolation and methods

- Use fake provider/session objects, fake clocks, and temporary storage for unit
  tests. Fixtures must prevent real PowerShell/Fabric dispatch by default.
- Use deterministic Events/barriers for races and count dispatches; assert final
  states and generation, not only response codes. Add bounded test timeouts.
- Use FastAPI TestClient with injected dependencies/credentials for route tests.
  Exercise the route → validation → broker → provider outcome path, not only mocks
  that bypass the behavior under review. Audit files go into a temporary directory.
- Use harmless PowerShell function/module stubs and a no-network subprocess fixture
  to exercise error streams, caught/logged errors, no output, crash, restart and stall.
  Do not call production upstream operations to test the transport.
- Component tests use DOM interactions and controlled delayed responses. Browser
  smoke uses deterministic local fixture responses and also exercises real local
  proxy/client-auth wiring. A blanket browser mock must not bypass that wiring test.
- Archive concise sanitized logs/failure screenshots. Do not attach real tokens,
  tenant exports, or arbitrary unredacted provider stdout to repository reports.

## Required S01 matrix

| ID | Case and assertion | Method |
|---|---|---|
| C01 | Unknown verb/new command blocked; Publish/Approve/Revoke/Move/Restore/Enable/Disable cannot enter read executor | Catalog + builder + HTTP tests; dispatch count zero |
| C02 | Reviewed reads used by inventory/items/runs/Git still dispatch; unreviewed reads visible but blocked; admitted source drift blocks | Explicit reviewed fixtures + source fingerprint mutation |
| C03 | Only reviewed workspace create/update params allowed; CapacityId and other blocked writes rejected at preview/plan/dispatch | Catalog, command and route tests |
| C04 | Missing/blank/unknown/type/ValidateSet/exclusive params rejected before provider; false bool preserved; omitted switch distinct | Parameterized valid/invalid cases based on admitted schemas |
| C05 | Quotes, newlines, Unicode, arrays and hostile PowerShell-looking strings remain literal; non-finite numbers and unsupported objects rejected | Renderer assertions plus harmless PowerShell echo fixture |
| C06 | Baseline REST declarations compatible; malformed method/path/placeholder and blocked policy rejected | Shared parser, builder, diagnostics and route fixtures |
| C07 | Duplicate raw IDs and broken verification/provider/source references reported before merge hides them | Synthetic registries + real baseline assertions |
| O01 | Structured upstream success:false fails connect/read/validate/apply appropriately; domain error field preserved as data | Adapter and route contract tests |
| O02 | Terminating errors, caught/logged errors and WhatIf errors cannot become validation success | Harmless PowerShell stubs invoking the inspected wrapper/command behavior |
| O03 | Empty/null/array/object/plain text/mixed streams/malformed JSON interpreted by declared outcome contract | Provider fixture table; no generic blanket success |
| O04 | Valid inventory arrays and valid empty reads survive normalization without UI data loss | API + result-rendering fixtures |
| O05 | Same-tenant reconnect, failed reconnect, close and subprocess restart invalidate old session generation and plans | Stateful fake runtime + subprocess fixture |
| O06 | Queued read/validate/apply never dispatch into a replacement tenant/session | Barriers controlling session change at dispatch boundary |
| O07 | No-output stall exits by configured deadline; owned child/workers cleaned; no stale result reused; next operation requires valid auth generation | Real harmless subprocess with test time budget; inspect teardown |
| M01 | Mutating returned get/list/create DTOs cannot change stored approvals, including nested values | Detached object tests |
| M02 | Parameters, command, validation, verification, expiry/session or admitted source/catalog change causes digest/identity rejection | Tampered internal fixture; assert zero dispatch |
| M03 | Two simultaneous apply callers dispatch exactly once | Deterministic barrier race; terminal retry also rejected |
| M04 | Validate/validate and validate/apply races cannot grant approval twice or reopen terminal state | Per-attempt ownership tests |
| M05 | Expiry before claim/after queue wait prevents dispatch; expiry during apply does not rewrite active outcome | Fake clock + controlled provider |
| M06 | Wrong confirmation and validation failure cannot authorize apply | Broker and HTTP negative tests |
| M07 | Create verifies returned ID and expected fields; duplicate name/absent ID/wrong ID cannot be treated as verified creation | Create response/read-back fixture matrix |
| M08 | Update verifies specified ID and requested fields; empty apply can verify; unchanged unrelated fields are irrelevant | Update fixture matrix |
| M09 | Failed/uncertain apply and successful apply with failed/mismatched read-back have distinct truthful terminal states; no apply retry | Exceptions/timeout/provider/read-back failures |
| M10 | History/restart cannot restore reusable approvals; list/get remain responsive during blocked remote work | Temporary history + blocked fake provider |
| A01 | Missing/invalid client credential rejected for protected routes; only minimal health exempt | Real middleware route matrix |
| A02 | Foreign Host/Origin rejected at backend and frontend proxy; client header cannot override proxy credential | HTTP integration against both local listeners |
| A03 | Supported launcher/proxy can access API; credential absent from URL/bundle/localStorage/log/export; restart rotates it | Integration and browser checks with synthetic secret |
| A04 | Synthetic secrets in params, rendered command, nested data/errors/outputs never reach durable/exported history | Byte search in temporary log and exported content |
| A05 | Rejected request, connect/read failure, validation failure and apply/read-back outcome have run/attempt IDs, duration, honest status | End-to-end API/activity assertions |
| A06 | Oversized events, retention boundary, malformed/truncated lines and maximum history query are bounded and usable | Temp files near configured limits; assert bytes/read budget |
| A07 | Start-record write failure blocks mutation; outcome-record failure warns without replay; orphan start after restart shown unknown | Disk failure injection and history reconstruction |
| U01 | Tenant input edit differs from connected identity; reconnect/failure clears context and reusable approval | Component + browser interactions |
| U02 | Workspace change clears item; delayed old workspace/item/read/plan responses cannot restore stale UI | Deferred promise/API response tests |
| U03 | Only valid current confirmation enables apply; double click, expiry and terminal outcomes cannot re-submit | Workbench interaction + actual request count |
| U04 | All new mutation outcomes readable in workbench/Change Plans; unknown outcome instructs inspection without replay | Components with full state matrix |
| U05 | Offline catalog state visible; backend policy wins; navigation/empty/loading/failure/retry-read flows usable | Browser smoke |
| U06 | JSON/CSV exports preserve displayed data/quoting and safe filenames; activity exports are redacted; CSV formula-looking cells handled under documented export policy | Download content assertions including commas/newlines/formula prefixes |
| U07 | Keyboard reaches connect/form/confirmation actions; labels, error and status announcements accessible | Browser keyboard check plus DOM accessibility assertions |
| E01 | Clean supported install uses committed lock/constraints; compile/backend tests/frontend tests/build pass | Fresh temp checkout/environment; record versions and exact commands |
| E02 | Launcher rejects unsupported runtime/missing import/install failure/stale SkipInstall dependencies | Injectable command probes/native exit-code fixtures |
| E03 | API/UI port collisions/readiness timeout handled; startup failure cleans only owned children; no visible windows in unattended checks | Windows process/port fixtures |
| E04 | Editable install imports all provider subpackages in repository context; docs accurately state standalone-wheel limitation | Clean environment import/entrypoint test |
| E05 | CI path filters include relevant upstream changes and sprint branches; each test lane invoked; workflow parses | Workflow/path fixtures + local commands; remote CI result separately recorded |
| E06 | Version/docs/ignore rules consistent; no generated artifacts/secrets accidentally staged; branch/evidence revision matches | Diff/status review and packaging metadata checks |

## Live evidence, separately gated

| ID | Procedure when an explicitly designated environment is available | Completion evidence |
|---|---|---|
| L01 | Connect to designated test tenant; inventory workspaces/items/runs and read context switches | Sanitized operator report with permissions, revision and actual results |
| L02 | In an explicitly approved disposable workspace scope, create/update the allowed fields; inspect remote state and activity | Real returned workspace ID and comparisons retained privately/redacted; no inferred cleanup authorization |
| L03 | Later S02: run Security Audit with agreed target/permissions and inspect original report bundle | Auth method, safeguards/truncation, status and artifact validation |

S01 may be accepted as locally verified with L01/L02 NOT RUN, if the lead expressly
records that limit. Never manufacture a pass or make live writes merely to close
the matrix. Missing credentials should not stop the offline sprint.

## Commands and baseline

Current working backend command, from repository root on this Windows checkout:

```powershell
& .\studio\backend\.venv\Scripts\python.exe -m pytest -q studio/backend/tests
& .\studio\backend\.venv\Scripts\python.exe -m compileall -q studio/backend/app
```

Initial audit ran pytest from `studio/backend`: **27 passed in 26.22 seconds**.
This legacy suite is a baseline, not the new acceptance suite. The local default
PowerShell profile emitted a broken Conda error; use `pwsh -NoProfile`/non-login
shell and the explicit venv interpreter rather than repairing global Python here.

After P4, developer must document/install these scripts (they do not all exist now):

```powershell
Set-Location studio
npm ci
npm run test -w frontend -- --run
npm run build
npm run test:e2e -w frontend
```

Developer also supplies exact reproducible backend dependency install, PowerShell
fixture, and Windows launcher-test commands in the handoff report. Light first
checks they exist and verifies their exit codes; never records planned commands as
executed. Record runtime versions, OS, skipped tests, and whether each result was
mocked, subprocess-based, browser-based, or live.
