# Roles and delivery rules

## Ownership

| Role | Owns | Must not substitute for |
|---|---|---|
| Tech lead | Product architecture; feature order and rationale; contracts; concurrency and failure semantics; sprint scope; review of changed logic and affected callers; final acceptance | Independent test evidence |
| Medium developer | Implementation; meaningful regression tests with each change; dependency setup; integrated build; repairing defects; concise milestone checkpoints | Lead approval of a new architecture or widened execution policy |
| Light tester | Execute and extend the planned tests; reproduce defects; browser checks; evidence collection; branch/test inventory; backlog hygiene; concise review packet | Final judgment on locking, authentication, mutation semantics, or architecture |
| User | Product choices, environment/access decisions, model selection, interruption preferences | Repeated permission to continue approved routine work |

The lead may delegate bounded evidence gathering and mechanical review to the
light model. The lead still inspects the relevant code, provider contracts, and
negative paths personally. Developers cannot approve their own sprint. Passing
tests alone never closes a sprint.

## Work size and continuation

A sprint is a coherent, integrated outcome. A pass is a substantial implementation
milestone within it, not a separate user assignment. S01 has four passes that may
take hours each; these are scope boundaries, not promises about duration or a
requirement to burn time/tokens. The developer continues automatically after a
milestone once its checks pass, through all approved passes.

Do not stop after a component, commit, green unit test, or a progress update just
to ask for "next pass." Do not defer all testing to the light model: developer
regression checks protect each change; the light model independently challenges
the complete result later. Avoid large unrelated rewrites in the same pass.

Keep compact checkpoints at pass boundaries and before context/session exhaustion.
Resume the unfinished scope from the checkpoint. If a runtime requires a new user
turn, say so explicitly and supply the single resume instruction. Never promise
unattended hours when the host cannot run them.

After S01, record passes completed, approximate elapsed effort, substantive scope,
user interventions, and why each stop occurred. The lead adjusts later pass size
using this evidence and the user's feedback, not lines of code or token consumption.

## State and gates

`APPROVED_FOR_DEV → IN_DEV → READY_FOR_LIGHT_QA → IN_QA → READY_FOR_TECH_LEAD
→ ACCEPTED`

QA may return `CHANGES_REQUESTED → IN_DEV`; an architecture uncertainty is
`NEEDS_TECH_LEAD`; missing external evidence is `BLOCKED_EXTERNAL` for the affected
test/item only. Continue independent approved work. `ACCEPTED` requires the lead.
The lead then writes and approves the next sprint; future backlog proposals are
not permission to start implementing them.

- Developer gate: all passes integrated; own checks pass; known failures explicitly
  recorded; handoff report names the candidate SHA and working-tree changes.
- QA gate: independent matrix results; repros for failures; tests tied to exact
  source revision; no unreported skip; branch/backlog records updated.
- Lead gate: inspect diff and critical full call paths, review evidence and residual
  risks, request repairs or accept with clearly stated live-validation limits.
- Release/merge readiness: separate from local sprint acceptance; describe what was
  actually verified. The lead's review does not authorize an unspecified tenant write.

## Escalation rules

| Situation | Action |
|---|---|
| Expected regression, build failure, missing test dependency, clear UI bug | Developer repairs; light reports exact repro; no lead interruption needed |
| Locking/session lifecycle cannot meet the approved invariant; upstream transport needs replacement; hidden provider behavior makes outcomes ambiguous | Record evidence and options; ask lead; continue unrelated approved work |
| New write/admin permission, changed confirmation semantics, retrying an uncertain write, weaker validation to make tests pass | Ask lead before implementing that change |
| Repeated failure after two materially different repair attempts with no new evidence | Bring concise diagnosis to lead; do not spend hours cycling the same attempt |
| Missing credentials, designated tenant, product preference, or environment authorization | Ask user once with the specific dependency; keep local tests progressing |
| All four passes complete | Medium announces `READY_FOR_LIGHT_QA` with prompt/report paths |
| Independent QA complete with no unresolved required local failures | Light announces `READY_FOR_TECH_LEAD` and requests final logic audit |
| QA finds a safety/architecture defect even while other tests pass | Light announces `NEEDS_TECH_LEAD`, identifies failing invariant, attaches minimal repro |

When the user starts a role, that role may use available in-task delegation if the
configured environment supports the requested model. Do not silently substitute a
different model tier, create user-visible tasks, or claim automatic handoff happened
without a successful dispatch. Default to the user's medium → light → lead handoff.

## Branches and change ownership

Implement S01 on `codex/s01-reliability-foundation` based on the verified integration
branch, or continue there if it already exists. Check HEAD/status first; preserve
unrelated local work. Use the existing checkout where safe; isolation is an option
when concurrent work would conflict. Do not silently base work on a moving remote.

Make coherent local commits where supported; stage explicit owned paths. Record
base and candidate SHAs. Pushing, merging, deleting branches, or publishing is not
part of these role prompts unless separately requested. Light owns its test/report
changes and coordinates candidate updates with the developer. Re-test changed
behavior and affected suites after repairs; a result from an older SHA is historical.

The light model refreshes all refs in the local branch inventory, marks unrelated
upstream branches out of scope, and associates every relevant branch with test and
lead-review status. No need to run Studio tests on every upstream sample branch.
