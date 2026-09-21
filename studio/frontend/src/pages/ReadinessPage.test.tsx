import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test, vi } from 'vitest';
import { ReadinessPage } from './ReadinessPage';
import { ILLUSTRATIVE_FOIL_PROJECT } from '../data/foil-project';
import * as api from '../api/client';

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return { ...actual, getProjectReadiness: vi.fn() };
});

const report: api.ProjectReadinessReport = {
  project_id: 'foil',
  profile_name: 'dev',
  workspace_display_name: 'foil-dev',
  evaluated_at: '2026-09-21T00:00:00+00:00',
  deployable: false,
  authorization: false,
  summary: 'Runtime readiness is unresolved.',
  counts: { satisfied: 2, action_required: 1, unknown: 1, blocked: 0, not_applicable: 0 },
  checks: [
    { id: 'project.contract', category: 'Project', title: 'Project contract', status: 'satisfied', required: true, evidence_kind: 'local-contract', source: 'validator', detail: 'Local contract passed.' },
    { id: 'identity.fabric-session', category: 'Identity', title: 'Fabric authentication session', status: 'action_required', required: true, evidence_kind: 'none', source: 'backend', detail: 'Not connected.', next_action: 'Connect.' },
    { id: 'workspace.target', category: 'Workspace', title: 'Target workspace', status: 'unknown', required: true, evidence_kind: 'none', source: 'No provider observation', detail: 'Not observed.' },
    { id: 'deployment.owner', category: 'Deployment', title: 'Deployment ownership', status: 'satisfied', required: true, evidence_kind: 'local-contract', source: 'profile:dev', detail: 'Declared.' },
  ],
  bootstrap_actions: [
    { id: 'connect-fabric', category: 'Identity', title: 'Connect Fabric session', kind: 'user-action', executable: false, reason: 'Explicit operator action.' },
  ],
};

test('readiness keeps unknown distinct from missing and bootstrap actions non-executing', async () => {
  vi.mocked(api.getProjectReadiness).mockResolvedValue(report);
  render(<ReadinessPage project={ILLUSTRATIVE_FOIL_PROJECT} profileName="dev" contextKey="offline:dev" onProfileChange={vi.fn()} />);
  expect(await screen.findByText('Target workspace')).toBeInTheDocument();
  expect(screen.getByText('UNKNOWN')).toBeInTheDocument();
  expect(screen.getByText('PLAN ONLY')).toBeInTheDocument();
  expect(screen.getByText('Deployment authorized')).toBeInTheDocument();
  expect(screen.getByText('NO')).toBeInTheDocument();
  expect(screen.queryByText('MISSING')).not.toBeInTheDocument();
});

test('changing readiness profile is explicit and does not execute a bootstrap action', async () => {
  vi.mocked(api.getProjectReadiness).mockResolvedValue(report);
  const onProfileChange = vi.fn();
  render(<ReadinessPage project={ILLUSTRATIVE_FOIL_PROJECT} profileName="dev" contextKey="offline:dev" onProfileChange={onProfileChange} />);
  await screen.findByText('Target workspace');
  await userEvent.selectOptions(screen.getByLabelText('Readiness profile'), 'test');
  expect(onProfileChange).toHaveBeenCalledWith('test');
  expect(screen.queryByRole('button', { name: /execute/i })).not.toBeInTheDocument();
});

test('context change causes a fresh readiness evaluation', async () => {
  vi.mocked(api.getProjectReadiness).mockResolvedValue(report);
  const view = render(<ReadinessPage project={ILLUSTRATIVE_FOIL_PROJECT} profileName="dev" contextKey="offline:dev" onProfileChange={vi.fn()} />);
  await waitFor(() => expect(api.getProjectReadiness).toHaveBeenCalledTimes(1));
  view.rerender(<ReadinessPage project={ILLUSTRATIVE_FOIL_PROJECT} profileName="dev" contextKey="session-a:dev" onProfileChange={vi.fn()} />);
  await waitFor(() => expect(api.getProjectReadiness).toHaveBeenCalledTimes(2));
});
