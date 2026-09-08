# Fabric Ops Studio project management

This folder is the working agreement for the tech lead, medium development
model, and light test model. The user owns product priorities. The tech lead
owns architecture, sprint admission, code-logic acceptance, and the next sprint.

**Current decision: execute S01, the reliability foundation, before adding the
Security Audit runner.** S01 contains four substantial development passes.
The developer continues through all four; the light model independently tests
the integrated result; the tech lead then reviews the logic and closes the sprint.

## Start here

| Need | Read |
|---|---|
| Current state and next action | [STATUS.md](STATUS.md) |
| Product purpose and target architecture | [VISION_ARCHITECTURE.md](VISION_ARCHITECTURE.md) |
| Responsibilities, autonomy, escalation | [OPERATING_MODEL.md](OPERATING_MODEL.md) |
| Approved coding scope and milestones | [S01](sprints/S01-reliability-foundation.md) |
| Test cases, methods, evidence requirements | [TEST_STRATEGY.md](TEST_STRATEGY.md) |
| Ordered feature and defect backlog | [BACKLOG.csv](BACKLOG.csv) |
| Local/remote branch inventory and test association | [BRANCHES.md](BRANCHES.md) |
| Architecture decisions | [DECISIONS.md](DECISIONS.md) |
| Initial code audit and baseline evidence | [Baseline audit](reports/2026-09-08-baseline-audit.md) |
| Start development | [Medium prompt](prompts/MEDIUM_DEVELOPMENT.md) |
| Start independent QA | [Light prompt](prompts/LIGHT_TEST.md) |
| Return to the tech lead | [Lead prompt](prompts/TECH_LEAD_REVIEW.md) |
| Report format | [Report template](templates/REPORT.md) |

## Source of truth

User instructions take precedence. This folder determines **future work and
acceptance**. `studio/README.md`, source code, and tests describe current behavior;
the older roadmap checkboxes are implementation history, not proof of safety.
The existing `studio/docs/REVIEW_AND_ACTION_PLAN_2026-09-08.md` remains a historical
input. This folder refines its sequencing and adds findings from direct inspection.

Do not duplicate task lists in several documents. Task status lives in
`BACKLOG.csv`; current role/pass/handoff lives in `STATUS.md`; evidence lives in
dated reports. Sprint and architecture documents hold requirements. Link between
them. Update Studio's user documentation when implementation changes its behavior.

## Minimum user interaction

Tell the medium model: **"Read projectmanagement/prompts/MEDIUM_DEVELOPMENT.md
and execute the approved sprint."** It should perform all approved passes.
At its `READY_FOR_LIGHT_QA` handoff, give the light model its prompt. At
`READY_FOR_TECH_LEAD`, return here with the lead prompt. Routine red tests return
to the developer with a concrete repair list; architecture questions come to the lead.

These files organize work; they do not themselves schedule background execution
or switch models. If the host cannot continue or dispatch the next role, the model
must leave one exact next action and a checkpoint, without claiming work is running.
