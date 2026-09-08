import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test, vi } from 'vitest';
import { InventoryPage } from './InventoryPage';
import * as api from '../api/client';
vi.mock('../api/client', () => ({ executeCapability: vi.fn(), getSession: vi.fn() }));

test('late old workspace inventory is discarded and its browser read is aborted', async () => {
  let complete!: (value: api.ExecutionResponse) => void;
  let signal: AbortSignal | undefined;
  vi.mocked(api.executeCapability).mockImplementation((_id, _params, s) => { signal = s; return new Promise(resolve => { complete = resolve; }); });
  const capability: api.Capability = { id: 'items', title: 'Items', description: '', category: 'Items', provider: 'Fabric REST API', source: 'fixture', risk: 'read', execution_policy: 'read' };
  const props = { title: 'Items', description: 'Fixture', connected: true, capability };
  const view = render(<InventoryPage {...props} parameters={{ workspaceId: 'old' }} />);
  await userEvent.click(screen.getByRole('button', { name: 'Refresh' }));
  view.rerender(<InventoryPage {...props} parameters={{ workspaceId: 'new' }} />);
  expect(signal?.aborted).toBe(true);
  await act(async () => complete({ capability_id: 'items', provider: 'Fabric REST API', risk: 'read', rendered_command: 'old', result: { studio_envelope: 1, data: [{ id: 'old', displayName: 'Old workspace item' }] } }));
  expect(screen.queryByText('Old workspace item')).not.toBeInTheDocument();
});
