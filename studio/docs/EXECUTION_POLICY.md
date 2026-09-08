# Execution policy — S01 candidate

The current contract is in [Studio README](../README.md) and the approved
[S01 decisions](../../projectmanagement/DECISIONS.md).

Discovery never authorizes execution. Only reviewed source/contract manifests
admit reads. Guarded writes are suspended pending the lead decision on upstream
retries and HTTP 204 handling; no runtime flag lifts the suspension.

Candidate lifecycle: planned -> validating -> validated -> executing -> executed,
applied_unverified, failed, or outcome_unknown. Validation failure, expiry and
identity invalidation are terminal. Only the owning attempt may complete an
in-flight state. Expiry cannot relabel an already-dispatched apply. Reads and
claims check expected session at dispatch. No broker lock spans provider I/O.

Audit records action, opaque IDs, honest outcome and duration. It omits free-form
parameters, rendered commands and arbitrary error/result data. Live results may
contain provider data; exported activity remains sanitized.
