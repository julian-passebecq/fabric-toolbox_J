# S01 developer validation — 2026-09-08

Candidate: `79aedecccb5edcffb2b139aea61038e4b4c719d6`.
Base: `af1c13e56f6c4cbe24d469679e93068c891e6dbe`.
This is developer evidence, not independent QA or acceptance.

## Reproducible commands and evidence

Use Python 3.13, Node 22.12+ in major 22 and npm 10/11. The validation used
Windows 11 10.0.26200, Python 3.13.1, Node 22.22.0, npm 10.9.4, Vitest 4.1.11,
Playwright 1.58.2 / Chromium 145.0.7632.6, and the committed backend lock.

From repository root:

```powershell
python -m venv studio/backend/.venv
& ./studio/backend/.venv/Scripts/python.exe -m pip install -r studio/backend/requirements.lock
& ./studio/backend/.venv/Scripts/python.exe -m pip install --no-deps --no-build-isolation -e studio/backend
& ./studio/backend/.venv/Scripts/python.exe -m compileall -q studio/backend/app studio/scripts
& ./studio/backend/.venv/Scripts/python.exe -m pytest -q studio/backend/tests
# Focused real PowerShell outcome / transport / upstream-defect fixtures:
& ./studio/backend/.venv/Scripts/python.exe -m pytest -q studio/backend/tests/test_contracts.py studio/backend/tests/test_artifact_identity.py studio/backend/tests/test_rest_upstream.py studio/backend/tests/test_upstream_blockers.py studio/backend/tests/test_lifecycle.py
# Native process, port, runtime, dependency, and PowerShell parser checks:
& ./studio/backend/.venv/Scripts/python.exe -m pytest -q studio/backend/tests/test_launcher.py
Set-Location studio
npm ci
npm run test -w frontend -- --run
npm run build
npx -w frontend playwright install chromium
npm run test:e2e -w frontend
```

Actual fresh install used `D:/PROJ/s01-qa-2fe35a13`, an isolated detached checkout.
It was installed from 2fe35a13, then advanced to 192b6627 for integrated
checks and 79aedecc for final backend/launcher checks; dependencies, manifests and launcher installation contracts are unchanged
between those code commits. No dependencies or generated files were copied from
the original checkout. The first long TEMP checkout path failed on an unrelated
upstream sample's MAX_PATH; Git removed the failed worktree automatically.

```powershell
# In the clean checkout, with Node 22 on PATH:
./studio/scripts/start-studio.ps1 -NoBrowser -SmokeTest -PythonPath <Python313.exe> -ApiPort 18767 -UiPort 15175
./studio/scripts/start-studio.ps1 -NoBrowser -SkipInstall -SmokeTest -PythonPath ./studio/backend/.venv/Scripts/python.exe -ApiPort 18767 -UiPort 15175
```

The first command created the venv, installed the lock/editable package, ran npm ci,
verified dependencies/imports, started both services, reached the authenticated
proxy session endpoint, and cleaned its owned children (exit 0). Provider subpackages
import from the clean environment and installed metadata reports 0.8.0.

Final integrated transcripts:

- [Clean backend/compilation/launcher](S01-clean-backend.txt)
- [Clean component/build/browser checks](S01-clean-frontend.txt)

The frontend transcript is for 192b6627; the final two commits change only Python
PowerShell UTF-8 startup and regression assertions. Frontend source, dependencies,
and browser-facing contracts are unchanged. The first hidden clean backend run
found Unicode output replaced by question marks; explicit UTF-8 output, ASCII-safe encoded Unicode commands, and a
real persistent-session Unicode assertion repair that defect.

Each transcript includes the exact revision, command, directory, exit status and
measured duration. Final clean results:

- Backend: **144 passed**, two deprecation warnings, 70.38 s pytest time
  (71.55 s command wall time); compilation exit 0.
- Components: **17 passed** across three files, 107.45 s runner time.
- Frontend build: exit 0, 27.24 s command wall time.
- Browser: **4 passed**, 35.1 s runner time (56.18 s command wall time).
- Clean locked install/full launcher smoke: exit 0; final SkipInstall launcher
  readiness and owned-child cleanup: exit 0, 6.32 s.
- Built frontend contains no synthetic browser fixture credential.

There were no test skips. Starlette/httpx compatibility and anyio alias deprecation
warnings are recorded; no dependency-warning suppression was introduced. Remote CI
was not run. Test listeners were checked after completion; none remain.

## Required offline acceptance map

PASS below means executed local assertions, never a live-tenant claim. Candidate
write assertions lift admission only inside pytest or the separate no-network
browser fixture. Production suspension is independently asserted. The unresolved
upstream contract keeps production-dependent write rows BLOCKED even where the
candidate state machine fixtures pass.

| ID | Status | Executed evidence / limitation |
|---|---|---|
| C01 | PASS | test_contracts unknown verbs/baseline unsafe commands; test_api_contracts zero dispatch |
| C02 | PASS | test_catalog reviewed inventory/REST reads; test_contracts fingerprint drift; test_artifact_identity loaded AST drift |
| C03 | PASS | test_contracts CapacityId/type rejection; test_upstream_blockers production suspension cannot be overridden |
| C04 | PASS | test_contracts mandatory/blank/unknown/types/GUIDs/ValidateSet/exclusivity/false bool and switch assertions |
| C05 | PASS | test_contracts literal PowerShell round-trip with quotes/newline/Unicode/arrays/hostile text; non-finite/object rejection |
| C06 | PASS | shared parser fixtures, baseline diagnostics and actual module-scoped REST helper fixture |
| C07 | PASS | raw duplicate rejection and diagnostics duplicate/broken verification/endpoint/source checks |
| O01 | PASS | test_api_contracts failure connect/read/validation; domain error data retained; candidate apply failure fixtures |
| O02 | PASS | original workspace/logger bodies with harmless dependencies; terminating/nonterminating/caught error and WhatIf fixtures |
| O03 | PASS | declared-envelope shape table, malformed/plain/mixed rejection and explicit empty invocation handling |
| O04 | PASS | actual API helper unary-comma array fixture, inventory/component rows and downloaded JSON |
| O05 | PASS | same-tenant generation invalidation, failed reconnect route, real process loss and explicit reconnect requirement |
| O06 | PASS | deterministic queued read/validate/apply replacement-session fixtures; no replacement-tenant dispatch |
| O07 | PASS | real persistent pwsh success then 60-second stall bounded at 3 seconds; owned process/worker terminated and no stale reuse |
| M01 | PASS | detached create/get/list DTO mutation assertions |
| M02 | PASS | parameter/command/expiry/session/artifact/digest tampering and loaded-source fixture rejection |
| M03 | PASS | barrier-controlled apply race dispatches once; terminal retry rejected; real HTTP and browser request count |
| M04 | PASS | validation/validation and validation/apply races; no repeated validation of a validated plan |
| M05 | PASS | queued expiry blocks dispatch; expiry while applying cannot rewrite executing outcome |
| M06 | PASS | wrong confirmation and failed validation cannot authorize apply; actual API route tests |
| M07 | BLOCKED | Candidate returned-ID/field/duplicate/missing fixtures pass; real create cannot be admitted while upstream retries uncertain POST |
| M08 | BLOCKED | Candidate empty-update verification passes; original API helper throws on HTTP 204 |
| M09 | BLOCKED | Candidate failure/unknown/read-back states pass; upstream still loses sufficient definitive-vs-uncertain failure evidence and retries writes |
| M10 | PASS | list/get stay responsive during blocked fake I/O; approvals remain memory-only; historical starts cannot recreate them |
| A01 | PASS | protected route matrix and minimal health, missing configuration fails closed |
| A02 | PASS | direct API and real proxy Host/Origin rejection; client credential override stripped |
| A03 | PASS | actual launcher/proxy readiness and fresh launch credential flow; browser URL/storage checks; server-only credential configuration |
| A04 | PASS | nested synthetic secrets omitted from durable activity and legacy/export serialization |
| A05 | PASS | route/provider failures and mutation attempts have UUIDs, honest statuses and durations |
| A06 | PASS | rotation, record/read/query limits, malformed and oversized tail records |
| A07 | PASS | start-write failure blocks apply, outcome-write failure retains result/warning/no replay, orphan start becomes unknown |
| U01 | PASS | browser keyboard connect, editable tenant draft and failed reconnect clear target state |
| U02 | PASS | delayed plan/inventory promises discarded, old browser read aborted, context identity remounts operation state |
| U03 | PASS | typed approval, double click, past expiry and terminal outcome assertions; one apply request |
| U04 | PASS | all eleven status announcements, unknown inspection instructions and disabled terminal controls |
| U05 | PASS | offline catalog/browser smoke; stale selected offline metadata replaced with live backend metadata |
| U06 | PASS | actual JSON/CSV downloads preserve fixture data and quoting; formula prefix and safe filename assertions |
| U07 | PASS | keyboard reaches connect, labeled fields/confirmation, error/status ARIA assertions and browser workflow |
| E01 | PASS | fresh repository checkout/venv, locked npm ci, package imports, integrated transcript commands |
| E02 | PASS | missing tool/unsupported Node/native failure/stale SkipInstall tests plus clean installed import/dependency checks |
| E03 | PASS | real port collision/timeout/dead-child/owned-child fixtures; two-listener launcher readiness and cleanup |
| E04 | PASS | clean editable package imports providers; repository runtime limitation documented |
| E05 | PASS | workflow parses and asserts provider/sprint filters and all lanes; corresponding local commands run; remote result NOT RUN |
| E06 | PASS | 0.8.0 versions, lock and narrow ignores; explicit staged-path review; candidate/log identity |
| L01 | NOT RUN | No designated live tenant |
| L02 | NOT RUN | No designated disposable write scope; production writes suspended |
| L03 | NOT RUN | Future S02, not authorized |

## Upstream blocker evidence

`test_upstream_blockers.py` executes the original API helper with a harmless
Invoke-RestMethod stub and counts invocations. HTTP 503 and 504 each produce four
POST calls even with MaxRetries=0; HTTP 204 produces one call then throws. The
configuration defaults use integerpositive validation, so setting global retry
configuration to zero is not a reviewed supported fix. Do not use a negative count
as an undocumented bypass. The lead must authorize the upstream contract repair.

## Explicit verification limits

- No live authentication, inventory or mutation. No tenant outputs or secrets were
  used as fixtures. Browser writes use a separately enabled in-memory fixture only.
- The upstream-module artifact fixture dot-sources definitions, without executing
  production operations. It proves comparison logic, not a live installed tenant module.
- Some acceptance cases share contract/dispatch implementations and fixtures; light
  QA must independently challenge missing combinations before any lead acceptance.
- Clean-checkout logs and the working fixture screenshot are retained locally. The
  detached clean checkout is retained for reproduction; no background work remains
  after the final report. A future lead decision may require a new candidate.
