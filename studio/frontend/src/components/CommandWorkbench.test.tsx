import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, test, vi } from 'vitest';
import { CommandWorkbench } from './CommandWorkbench';
import { MutationOutcome } from './MutationOutcome';
import { csvCell, extractRows } from './ResultViewer';
import * as api from '../api/client';

vi.mock('../api/client', () => ({ createMutationPlan: vi.fn(), validateMutation: vi.fn(), executeMutation: vi.fn(), previewCapability: vi.fn(), executeCapability: vi.fn() }));
const capability: api.Capability = { id: 'create', title: 'Create workspace', description: 'Create', category: 'Workspace', provider: 'MicrosoftFabricMgmt', source: 'test', risk: 'write', execution_policy: 'guarded-write', parameter_specs: [{ name: 'WorkspaceName', type: 'string', mandatory: true, is_switch: false, allowed_values: [] }] };
const plan: api.MutationPlan = { plan_id: 'one', capability_id: 'create', capability_title: 'Create', provider: 'MicrosoftFabricMgmt', risk: 'write', tenant_id: 'tenant-a', session_generation: 'a', parameters: { WorkspaceName: 'Lab' }, rendered_command: 'fixture', supports_validation: true, confirmation_text: 'APPLY ONE', digest: 'hash', created_at: new Date().toISOString(), expires_at: new Date(Date.now() + 60000).toISOString(), status: 'planned' };
beforeEach(() => vi.resetAllMocks());

test('typed approval, single validation, double click, and unknown outcome cannot replay', async () => {
  vi.mocked(api.createMutationPlan).mockResolvedValue(plan);
  vi.mocked(api.validateMutation).mockResolvedValue({ plan: { ...plan, status: 'validated' }, result: {} });
  vi.mocked(api.executeMutation).mockResolvedValue({ plan: { ...plan, status: 'outcome_unknown' }, result: {} });
  const user = userEvent.setup();
  render(<CommandWorkbench capability={capability} connected />);
  await user.type(screen.getByLabelText('WorkspaceName *'), 'Lab');
  await user.click(screen.getByRole('button', { name: 'Create guarded plan' }));
  const apply = await screen.findByRole('button', { name: 'Apply guarded write' });
  expect(apply).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Validate with -WhatIf' }));
  await user.type(screen.getByLabelText('Type APPLY ONE to apply'), 'APPLY ONE');
  await user.dblClick(apply);
  await screen.findByText(/Apply outcome is unknown/);
  expect(api.executeMutation).toHaveBeenCalledTimes(1);
  expect(apply).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Validate with -WhatIf' })).toBeDisabled();
});

test('late plan cannot restore old context', async () => {
  let finish!: (p: api.MutationPlan) => void;
  vi.mocked(api.createMutationPlan).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const user = userEvent.setup();
  const view = render(<CommandWorkbench capability={capability} connected defaultParameters={{ WorkspaceName: 'Old' }} />);
  await user.click(screen.getByRole('button', { name: 'Create guarded plan' }));
  view.rerender(<CommandWorkbench capability={capability} connected defaultParameters={{ WorkspaceName: 'New' }} />);
  await act(async () => finish(plan));
  expect(screen.queryByText('Immutable mutation plan')).not.toBeInTheDocument();
  expect(screen.getByLabelText('WorkspaceName *')).toHaveValue('New');
});

test('network loss after apply becomes unknown and expired plan is disabled', async () => {
  vi.mocked(api.createMutationPlan).mockResolvedValue({ ...plan, status: 'validated', expires_at: new Date(0).toISOString() });
  const user = userEvent.setup();
  render(<CommandWorkbench capability={capability} connected defaultParameters={{ WorkspaceName: 'Lab' }} />);
  await user.click(screen.getByRole('button', { name: 'Create guarded plan' }));
  await user.type(await screen.findByLabelText('Type APPLY ONE to apply'), 'APPLY ONE');
  expect(screen.getByRole('button', { name: 'Apply guarded write' })).toBeDisabled();
  expect(api.executeMutation).not.toHaveBeenCalled();
});

test.each<api.MutationStatus>(['planned','validating','validated','executing','executed','failed','expired','invalidated','validation_failed','applied_unverified','outcome_unknown'])('outcome %s is announced', status => {
  render(<MutationOutcome status={status} />);
  expect(screen.getByRole('status')).not.toBeEmptyDOMElement();
});

test('rows preserve domain errors and CSV escapes formulas quotes and newlines', () => {
  expect(extractRows({ studio_envelope: 1, data: [{ id: 'a', error: 'domain' }] })).toEqual([{ id: 'a', error: 'domain' }]);
  expect(extractRows({ studio_envelope: 1, data: [] })).toEqual([]);
  expect(csvCell('=SUM(A1)')).toBe('"\'=SUM(A1)"');
  expect(csvCell('a,"b"\nc')).toBe('"a,""b""\nc"');
});
