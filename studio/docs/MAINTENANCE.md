# Maintenance model

Fabric Ops Studio is designed to remain maintainable when Microsoft Fabric Toolbox and Fabric REST APIs change.

## Rule 1: upstream code stays upstream

Do not copy implementations from `tools/MicrosoftFabricMgmt`, `tools/fabric-security-audit`, `tools/fabric-assessment-tool`, or other upstream tools into Studio unless there is a documented reason.

Studio owns adapters, metadata, validation, UI and orchestration. Upstream tools own their domain implementation.

## Rule 2: every capability has provenance

Each capability must expose at minimum:

- source/provider
- source repository or official API family
- local upstream path where applicable
- command or REST endpoint
- risk classification
- integration type

## Rule 3: generated catalog vs curated metadata

The PowerShell catalog is discovered from `tools/MicrosoftFabricMgmt/source/Public/**/*.ps1`.

Generated entries provide broad coverage. Curated entries add better labels, descriptions, documentation, examples, parameter validation and explicit risk overrides.

Generated metadata must never silently overwrite curated metadata.

## Rule 4: updates

When syncing `main` from `microsoft/fabric-toolbox`:

1. merge/rebase the upstream changes into the fork
2. run the Studio capability discovery tests
3. inspect newly added/removed/renamed public PowerShell commands
4. review any capabilities whose risk classification changed
5. update curated metadata only where the generated description is insufficient
6. update source registry only when a provider or integration strategy changes

## Rule 5: provider boundaries

Preferred order:

1. MicrosoftFabricMgmt
2. official Fabric REST API
3. existing Fabric Toolbox specialized tool
4. Studio-owned implementation

A Studio-owned implementation should include a short rationale explaining why no upstream provider was suitable.

## Rule 6: safe execution

Execution must remain disabled for a provider until it has:

- parameter validation
- operation preview
- risk classification
- explicit confirmation rules for write/admin/destructive actions
- structured execution result
- activity/audit logging
- secret redaction

Read-only operations can be enabled first.

## Rule 7: no analytical authoring creep

Do not add DAX optimization, semantic-model editing, measure editing or report-canvas authoring. Keep report/model items only where they matter operationally: inventory, lineage, permissions, Git, deployment, monitoring and lifecycle management.
