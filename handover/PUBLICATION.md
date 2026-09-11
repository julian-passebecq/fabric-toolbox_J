# Preservation, provenance and verification

Audit date: 2026-09-11. Destination: `julian-passebecq/fabric-toolbox_J` on GitHub (`origin`), never the Microsoft `upstream` remote.

## Git inventory before publication

`origin` was fetched successfully. `main` and `origin/main` matched at `cee092b2`; `fabric-ops-studio-v1` and its origin branch matched at `af1c13e5`. Studio baseline history was already on GitHub. Five commits on local `codex/s01-reliability-foundation` were absent from origin:

| Commit | Preserved work |
|---|---|
| `2fe35a13` | S01 reliability implementation and unsafe-write suspension |
| `192b6627` | Provider failure recording and race fixtures |
| `be016756` | Hidden PowerShell Unicode handling |
| `79aedecc` | ASCII-safe Unicode command transport; final code candidate |
| `486d646f` | Planning, development handoff and validation evidence |

The takeover branch descends from `486d646f` and includes all five. Two untracked documents are included: root `AGENTS.md` and `studio/docs/REVIEW_AND_ACTION_PLAN_2026-09-08.md`. The original development branch is also being published to preserve its exact checkpoint. Integration/main remain unchanged; nothing is merged or deployed by this pass.

Registered worktrees: `D:/PROJ/fabric-toolbox_J` and clean detached `D:/PROJ/s01-qa-2fe35a13` at `79aedecc`. The detached commit is already an ancestor of the handover. No stashes; `git fsck --no-reflogs --unreachable` reported no recoverable unreachable objects. No other local development branches exist. Upstream remote-tracking branches are external Toolbox history, not missing Codex work to push into the fork.

## Prior Codex work inspected

The local task registry identified three earlier project tasks, all using the same repository checkout, including archived-task matching. Their completed histories were inspected. No additional project agent checkout was identified.

| Task | Contribution |
|---|---|
| Plan RPEO test improvements (`01a0822a-8275-7d11-bb74-bc03b86ee6c2`) | Read original handoff, baseline tests and failure probes, initial review document. |
| Plan AI development sprints (`01a08245-e835-7480-bd37-e1f37b0c66d6`) | Tech-lead architecture, backlog, S01 requirements, test strategy and role workflow. |
| S01 developer (`01a0825a-5630-7e21-9465-3815cc839240`) | Four S01 passes, implementation commits, clean-checkout validation and blocker handoff. |

Git records Julian Passebecq as author of the five commits; task/report evidence attributes the work to Codex roles. Exact originating AI authorship of older v0.7 commits is not established here. No independent light-QA completion was found. Other projects' current handover tasks are outside this repository's scope.

## Tests: evidence, not a new certification

Recorded on 2026-09-08: **144 backend tests, 17 component tests and four browser tests passed**; Python compilation, frontend build and fresh-install/launcher smoke passed. Backend/launcher final candidate is `79aedecc`; frontend evidence is `192b6627`, followed only by Python transport fixes. See committed [backend transcript](../projectmanagement/reports/S01-clean-backend.txt), [frontend transcript](../projectmanagement/reports/S01-clean-frontend.txt) and [acceptance map](../projectmanagement/reports/S01-validation.md) for exact commands and limits.

This preservation pass changes documentation only and does not rerun the full suite. It checks repository inventory, document links, diff whitespace and remote publication. No live tenant access or credentials are available as part of the handover. Two deprecation warnings were recorded in prior backend testing. The default local PowerShell profile also produced a broken Conda import during this audit; profile-free commands worked. This is a local shell setup issue, not evidence of an app failure.

## Local-only material

Virtual environments, node_modules, builds, caches, runtime/install state, logs and browser output remain ignored and are not needed to recover source. Runtime state can contain per-launch credentials and is intentionally not published. The useful ignored `studio/.run/validate_clean.py` is preserved verbatim as [archive/validate_clean.py](archive/validate_clean.py). It has machine-specific paths and overwrites historical transcripts: reference only, not the recommended portable runner. Use commands in the validation map.

The initial input archive was `C:/Users/julia/Downloads/Fabric_Ops_Studio_Codex_Handoff_2026-09-08.zip`; its product direction and audit conclusions are represented in the repository documents. Raw private Codex conversations, account databases and that original input archive are not published. No additional source push by the user is known to be required; tenant designation/credentials and any desired original archive transfer are separate from Git source preservation.

Final server verification and CI observation are recorded in `PUSH-RESULT.md` after publishing.
