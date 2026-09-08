# Audit the sprint and decide what comes next

Act as tech lead. Read STATUS, active sprint, architecture/decisions, development
handoff, light QA report/lead packet, backlog and branch/test inventory. Verify
their SHAs against the actual checkout and compare the sprint base to candidate.
The light model's report supports your review; it does not replace it.

Personally inspect changed logic plus affected full call paths: request admission,
source/provider contract, parameters and quoting, session generation at dispatch,
atomic claims/lock order/expiry, mutation uncertainty/verification, audit failure
behavior, client boundary, and frontend context invalidation. Inspect the upstream
implementations relied on by admitted operations, including failure/empty outputs
and the identity of the loaded module. Review tests for false confidence and mocks
that bypass the risk. Use targeted additional probes where evidence is missing.

You may ask the light role for bounded reproduction, inventories, running tests
or evidence formatting. Retain judgment on architecture, concurrency and semantics.

Write `projectmanagement/reports/S01-tech-lead-review.md` with a verdict:

- CHANGES_REQUESTED: concrete defects, priority, code pointers, reasoning,
  acceptance checks, repair scope and next owner. No premature next sprint.
- ACCEPTED: exact accepted code revision, invariants reviewed, validation evidence,
  residual/live-test limits and any explicitly deferred items.
- NEEDS_DECISION: evidence, options, recommendation and who must decide.

Only after acceptance, close evidenced backlog rows, update branch/review state,
and author the next sprint with purpose, architecture, substantial passes, tests,
milestones and handoff gates. Use measured developer effort/user interventions to
adjust pass sizing. The proposed next feature is the Security Audit vertical slice;
reassess its size against actual transport/auth readiness before approving it.

Never equate green tests with correct code, local acceptance with live production
validation, or an approved sprint with permission to publish/merge or mutate an
unspecified tenant. End with one clear next action for the user/model.
