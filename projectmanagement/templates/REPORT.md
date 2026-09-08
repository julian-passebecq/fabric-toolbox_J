# <Sprint / role / date>

## Verdict and next action

State: <IN_DEV / READY_FOR_LIGHT_QA / CHANGES_REQUESTED /
NEEDS_TECH_LEAD / READY_FOR_TECH_LEAD / ACCEPTED-by-lead-only>.
Next owner and exact prompt/action: <...>.

## Source identity

- Branch, sprint base SHA, candidate SHA, diff range:
- Dirty/untracked changes and ownership:
- OS/runtime/tool versions:
- Tested code revision versus report-only commits:

## Outcome

What works now, why it changed, and remaining limits. Keep the lead packet short;
link detailed matrix/logs rather than pasting all output.

## Acceptance evidence

| Matrix ID / backlog ID | PASS/FAIL/BLOCKED/NOT RUN | Command or procedure | Revision | Evidence path | Duration |
|---|---|---|---|---|---|
| <ID> | <state> | <exact reproducible command> | <SHA> | <sanitized log/assertion/test> | <time> |

Distinguish unit mocks, real harmless subprocesses, API integration, browser and
live Fabric results. List skips and reason; never silently count them as passed.

## Findings / repairs

| Finding ID | Severity | Expected → actual | Repro and code pointer | Owner | Status |
|---|---|---|---|---|---|
| <ID> | <P0/P1/P2> | <behavior> | <path:line + input/test> | <role> | <state> |

## Logic and decisions for lead attention

Critical files/call paths; invariants; lock order; identity/dispatch checks;
uncertain outcomes; dependencies; alternatives needing a decision. Separate a
reproduced defect from a plausible concern.

## Branch and backlog maintenance

Updated IDs, current candidate/review state, deferred proposals with rationale.
Do not duplicate the entire backlog here.

## Effort and continuation

Passes completed; approximate effort; user interruptions and reasons; next precise
step if unfinished; active processes owned by this run; cleanup performed.
