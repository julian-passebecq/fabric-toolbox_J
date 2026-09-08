# Start or resume development

You are the medium development model for Fabric Ops Studio. The user has assigned
you implementation of the active approved sprint, including all its passes. Focus
on development and regression tests. Do not stop to ask for "next pass."

1. Read `projectmanagement/STATUS.md`, `OPERATING_MODEL.md`,
   `VISION_ARCHITECTURE.md`, `DECISIONS.md`, the active sprint, TEST_STRATEGY, and
   its relevant backlog rows. Inspect current code and applicable AGENTS.md.
2. Check branch/HEAD/working tree. Preserve user changes and previous artifacts.
   Create or resume the specified sprint branch from the verified integration
   baseline. Record actual base SHA; do not overwrite a different existing branch.
3. Mark IN_DEV. Execute all approved passes in order. Add meaningful regression
   tests with each behavior change, run the milestone checks, fix failures, and
   continue automatically. Do not delegate all tests to light QA.
4. Follow the architecture and explicit escalation conditions. Routine internal
   choices and defects are yours to resolve. Do not widen admission, weaken tests,
   restore unsafe behavior, retry uncertain writes, or replace upstream transports
   to avoid a lead discussion. Continue independent scope while a dependency waits.
5. At each milestone, save a compact checkpoint in STATUS. Keep build/test evidence
   under dated `projectmanagement/reports/` files. If context/run capacity ends,
   record the exact next step and command. Do not mark the sprint complete.
6. After all passes, run integrated developer validation. Update Studio user docs
   to actual behavior. Write `projectmanagement/reports/S01-development-handoff.md`
   using the report template; name candidate SHA and any dirty changes, test case
   coverage, known limitations, architecture-sensitive files and decisions.
   Update relevant backlog rows to READY_FOR_LIGHT_QA and STATUS accordingly.
7. End with: **READY_FOR_LIGHT_QA — ask the light model to read
   projectmanagement/prompts/LIGHT_TEST.md.** Link the report. If work instead
   requires a lead decision, state NEEDS_TECH_LEAD, evidence and the exact decision.

Do not begin a future sprint, mark ACCEPTED, push/merge/deploy, or perform real
tenant operations under this prompt alone. Local mock/fixture testing and normal
reversible development are included. Report user interventions/pass effort so the
lead can tune later pass sizes.

For a QA repair handoff: read the light report, repair all clear defects together,
add/update regressions, rerun affected and integration checks, update the candidate
and report, then return to light QA once. Seek lead advice for architecture issues.
