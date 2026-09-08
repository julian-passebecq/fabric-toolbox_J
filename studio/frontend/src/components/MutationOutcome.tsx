import type { MutationStatus } from '../api/client';

const messages: Record<MutationStatus, string> = {
  planned: 'Plan created. Validate before applying.',
  validating: 'Validation is in progress.',
  validated: 'Local WhatIf completed. Remote permissions and apply success are not guaranteed.',
  executing: 'Apply is in progress. Do not submit again.',
  executed: 'Applied and verified against the requested workspace fields.',
  applied_unverified: 'Applied, but read-back could not verify the requested state. Inspect the workspace before any further change.',
  failed: 'Apply was not confirmed successful. Inspect the recorded outcome.',
  outcome_unknown: 'Apply outcome is unknown. Inspect the workspace and activity before any further change. This plan cannot be replayed.',
  validation_failed: 'Validation failed. This plan cannot be applied.',
  expired: 'Plan expired. Create a new plan if the change is still needed.',
  invalidated: 'Plan identity changed. Create a new plan in the current session.',
};

export function MutationOutcome({ status }: { status: MutationStatus }) {
  return <p role="status">{messages[status] ?? status}</p>;
}
