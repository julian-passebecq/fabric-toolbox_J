# Branch and verification register

Snapshot: 2026-09-08, locally available refs only. No fetch/push/merge performed
for this planning task. Full inventory: [branch-inventory.csv](branch-inventory.csv).
Remote-tracking refs are observations from the last local fetch, not evidence that
the server still has the same HEAD or that CI passed there.

| Branch/ref | Baseline observed | Purpose | Verification | Next owner/action |
|---|---|---|---|---|
| `fabric-ops-studio-v1` | `af1c13e5` | Studio integration branch; preserved base | 27 backend tests pass; P0 defects reproduced; no live validation | Medium starts S01 from verified baseline |
| `origin/fabric-ops-studio-v1` | `af1c13e5` | Tracking ref matches local Studio branch | No new remote CI result retrieved | Light records freshness and eventual candidate |
| `main` | `cee092b2` | Upstream-aligned fork base | Studio absent from this baseline; Studio QA not applicable | Preserve upstream alignment |
| `origin/main`, `upstream/main` | `cee092b2` | Locally observed upstream bases | Studio QA not applicable | No merge planned in S01 |
| `codex/s01-reliability-foundation` | `79aedecccb5edcffb2b139aea61038e4b4c719d6` | S01 code candidate; current branch | Developer evidence in S01 validation report | Tech lead resolves upstream write contract |
| Other `upstream/*` branches | See CSV | Toolbox sample/tool/update branches outside this sprint | NOT ASSESSED; not a failing Studio test result | Inventory only unless their changes enter Studio dependencies |

At this snapshot `main...fabric-ops-studio-v1` is 0 commits unique to main and 131
unique to Studio. The diff is 46 files / 5,351 insertions, in `studio/` and Studio CI.

## Candidate ledger

| Sprint | Implementation branch | Base SHA | Candidate SHA | Developer checks | Light QA | Lead verdict | Evidence |
|---|---|---|---|---|---|---|---|
| S01 | `codex/s01-reliability-foundation` | `af1c13e56f6c4cbe24d469679e93068c891e6dbe` | `79aedecccb5edcffb2b139aea61038e4b4c719d6` | See S01-validation.md | NOT RUN | NEEDS_TECH_LEAD | reports/S01-development-handoff.md |

Light updates this ledger for every candidate/rework cycle. Keep old candidate
results as history, not the current status. Reports must identify uncommitted source
changes: a HEAD alone cannot describe a dirty tested tree. Prefer an explicit clean
code candidate before independent QA; documentation evidence may follow with its
relationship stated.

To refresh the inventory without network changes, use `git for-each-ref` over
`refs/heads` and `refs/remotes`, recording ref, SHA, upstream, purpose, test state,
review state, last-observed date and report. Include symbolic default refs as aliases.
Never infer test or merge status from branch names.
