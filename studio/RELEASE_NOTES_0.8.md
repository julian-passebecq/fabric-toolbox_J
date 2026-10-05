# Fabric Ops Studio 0.8 — read-only milestone

This release candidate provides a local Windows operations console for reviewed
Fabric reads. It includes workspace, workspace-role, capacity and connection
inventory; item details/connections, job runs/schedules and Git status; result
exports, source provenance, diagnostics and bounded activity history.

All production writes are disabled, including workspace create/update. Catalog
visibility does not authorize execution. Security Audit, Assessment and Lineage
remain discovery/entrypoint surfaces; managed runners are future scope.

## Installation

Download the tagged source archive or clone the release tag. Use PowerShell 7,
Python 3.13, Node 22.12 or newer in major 22, and npm 10 or 11. From the repository
root run `./studio/scripts/start-studio.ps1`. Keep the launcher running. The
supported runtime requires the Toolbox checkout; no standalone installer is
provided. Consult [README.md](README.md) for setup, lifecycle and troubleshooting.

## Reliability changes

- Fail-closed source/parameter admission and normalized provider results.
- Session generation checks and bounded owned PowerShell process lifecycle.
- Per-launch local credential and Host/Origin checks on API and proxy.
- Bounded activity summaries, context-safe UI and JSON/CSV exports.
- Locked cross-platform native frontend dependencies for Windows/Linux CI.
- API, diagnostics and Overview accurately describe the read-only boundary.

## Validation limits

Offline fixtures exercise provider, API, browser and launcher behavior without
Fabric access. A passing fixture suite does not prove live authentication or
provider compatibility with a particular tenant. No tenant authentication,
inventory or mutation was performed for this release. This is a prerelease for
operator evaluation. The original S01 write requirements remain deferred because
upstream retries uncertain writes and rejects successful HTTP 204 responses.
