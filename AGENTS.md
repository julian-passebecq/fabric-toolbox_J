# Fabric Ops Studio coordination

2026-09-11 takeover: read `handover/README.md` first. The user has retired the
multi-agent workflow for cost reasons and wants a single Pro AI successor.
Historical role prompts remain reference material, not required agent dispatch.
Existing sprint scope and execution safety limits remain in force.

For work on Fabric Ops Studio (`studio/`), its CI, or project planning, start with
`projectmanagement/README.md` and `projectmanagement/STATUS.md`. They identify the
active sprint, role instructions, architecture, tests, and handoff state.

The user chooses the role: tech lead, medium development model, or light test
model. Follow that role's prompt in `projectmanagement/prompts/`. A normal
development request does not authorize executing future, unapproved sprints.
Complete all passes of the active approved sprint without requesting a new
prompt at each pass. Keep a resumable checkpoint if interrupted.

Keep upstream Toolbox implementations separate from Studio orchestration.
These coordination instructions do not impose Studio's backlog on unrelated
Toolbox samples or tools. Existing user instructions take precedence.
