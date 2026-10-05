# S01 successor review — 2026-10-05

## Verdict

NEEDS_DECISION for the original write-capable S01 scope. The user requested a
release; the successor prepared a separately scoped read-only 0.8 prerelease.
Workspace write acceptance and all later proposed sprints remain deferred.

Reviewed candidate: `cc88570d6dd0e8371853b8f9a1088e2dda07b396` on
`codex/release-0.8-readonly`. Base source: `79aedecc`; takeover base: `d85d568b`.
The single-successor agreement supersedes historical multi-model dispatch.
No independent-model QA or tenant certification is claimed.

## Critical paths reviewed

Admission checks source/contract fingerprints and retains unconditional production
write suspension. Parameter validation rejects unsupported shapes, unknown names
and conflicting filters; command strings use quoted literals. REST executor checks
GET admission, endpoint shape and the coordinated expected session. Runtime checks
loaded provider source/AST identity, serializes session I/O, invalidates on process
loss and prohibits implicit authenticated restart. The bounded subprocess extension
kills and joins owned workers on timeout.

The local boundary checks Host/Origin and a per-launch server credential; the proxy
strips client-supplied credentials. Activity persists bounded structured summaries
without arbitrary provider output. Frontend context identity and cancellation are
covered by component/browser fixtures. Broker snapshots, claims, dispatch rechecks
and terminal completion were inspected, but writes are unavailable in this release;
fixture-only mutation tests are regression evidence, not production-write approval.

## Release repairs

- Correct API/session/Overview descriptions to the effective read-only boundary.
- Stop treating an empty write allowlist as a failed readiness requirement when
  production writes are suspended.
- Add the 49 absent native npm lock entries at their exact existing parent versions,
  preserving every original lock entry. A completeness probe checked all optional
  dependencies declared by Rollup/esbuild.
- Add an HTTP regression proving zero write admissions and rejection of both
  workspace write routes without any provider call beyond fixture connect.

## Evidence and limits

Local backend: 144 original tests passed after changes; the additional API suite
passed all four tests. Components: 17 passed. TypeScript/Vite build passed.
Browser: four passed via actual local proxy and harmless provider fixtures.
Windows launcher: full-install and SkipInstall smoke both passed on free ports
28765/25173; default occupied port 5173 was rejected without stopping its owner.
Built frontend contained no synthetic browser credential. Compilation and diff
whitespace checks passed.

Final-candidate remote Ubuntu lane: 145 backend tests, 17 component tests, build
and four browser tests passed. Windows lane also concluded SUCCESS, including all launcher checks:
https://github.com/julian-passebecq/fabric-toolbox_J/actions/runs/37252347044

No real tenant authentication, inventory or mutation was performed. The unsupported
upstream write retry/204 contract remains a blocker for admitting production writes.
No P0/P1 defect was identified within the read-only prerelease boundary reviewed
here. The prerelease supports repository-based local operation, not a standalone
installer or multi-user service. This verdict does not close the original S01
write-dependent backlog or authorize the next sprint.

## Published read-only candidate

`studio-v0.8.0-rc.1` was published at the exact reviewed candidate after both CI
lanes concluded SUCCESS. The read-only prerelease boundary is accepted for offline
operator evaluation, with the live limits above. This is not full S01 acceptance.
See [release checkpoint](2026-10-05-release-0.8.md) for the tag/publication evidence.

Next action: evaluate the prerelease; designate a tenant for a separately scoped
live read smoke if desired. Production write admission remains suspended.
