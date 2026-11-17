# Fabric Ops Studio on fabric-toolbox_J

A fork of the Microsoft Fabric Toolbox. Our own product is Fabric Ops Studio in `studio/` (backend plus a React frontend), a management and operations UI over the Toolbox. Start with `studio/README.md` and `projectmanagement/STATUS.md`; `handover/` and the role prompts in `projectmanagement/prompts/` are history.

## Build and test
- `cd studio && npm ci`, then the component tests, build and `npm run test:e2e -w frontend`; the backend steps are in `.github/workflows/studio-ci.yml`.
- CI: GitHub Actions `studio-ci.yml` (public repo). No GitLab mirror.

## Guidelines
- Keep the upstream Toolbox samples and tools separate from Studio code, so merges from upstream stay clean.
- Studio talks to real Fabric tenants: no live tenant write, paid resource or stored credential without the owner asking for it.

How work flows: the fleet guideline every session loads (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`). CI recipe and runners: datapass-fleet-facade `AGENTS.md`.
