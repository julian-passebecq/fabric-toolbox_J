# Execution policy

Fabric Ops Studio begins in inspect-only mode. Execution is enabled incrementally by provider and risk level.

## Risk levels

- `read`: no state mutation
- `write`: creates or updates Fabric state
- `admin`: requires elevated tenant/workspace permissions or changes access/governance state
- `destructive`: deletes, disconnects, removes assignments, or otherwise risks irreversible loss

## Enablement order

1. read-only MicrosoftFabricMgmt commands
2. read-only official REST operations
3. guarded write MicrosoftFabricMgmt commands
4. guarded official REST writes
5. specialized upstream tools
6. destructive operations last

## Required controls

Every executable action must capture:

- provider
- source path or endpoint
- resolved parameters with secrets redacted
- risk level
- start/end timestamps
- result status
- error details

Write/admin/destructive actions must show a preview before execution. Destructive actions require an explicit second confirmation.
