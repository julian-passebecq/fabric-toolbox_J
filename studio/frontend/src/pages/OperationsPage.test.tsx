import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { OperationsPage } from './OperationsPage';
import type { Capability } from '../api/client';

test('live catalog replaces an already selected offline capability and populates context', async () => {
  const offline: Capability = { id: 'workspace', title: 'Workspace', description: '', category: 'Workspace', source: 'fixture', provider: 'MicrosoftFabricMgmt', risk: 'read', execution_policy: 'blocked' };
  const props = { title: 'Operations', description: 'Fixture', connected: true, defaultParameters: { WorkspaceId: 'current-workspace' } };
  const view = render(<OperationsPage {...props} capabilities={[offline]} />);
  expect(screen.queryByRole('button', { name: 'Run read-only' })).not.toBeInTheDocument();
  const live: Capability = { ...offline, execution_policy: 'read', parameter_specs: [{ name: 'WorkspaceId', type: 'string', mandatory: true, is_switch: false, allowed_values: [] }] };
  view.rerender(<OperationsPage {...props} capabilities={[live]} />);
  expect(await screen.findByRole('button', { name: 'Run read-only' })).toBeEnabled();
  expect(screen.getByLabelText('WorkspaceId *')).toHaveValue('current-workspace');
});
