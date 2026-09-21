import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test, vi } from 'vitest';
import { ILLUSTRATIVE_FOIL_PROJECT } from '../data/foil-project';
import { ProjectOverviewPage, reorderLayout } from './ProjectOverviewPage';

function renderPage(contextKey = 'session-a:dev', profileName = 'dev') {
  const onProfileChange = vi.fn();
  const view = render(
    <ProjectOverviewPage
      project={ILLUSTRATIVE_FOIL_PROJECT}
      profileName={profileName}
      contextKey={contextKey}
      onProfileChange={onProfileChange}
    />,
  );
  return { view, onProfileChange };
}

test('no live evidence is rendered as unknown rather than healthy', async () => {
  renderPage();
  await userEvent.click(screen.getByRole('button', { name: 'Observed / drift' }));
  expect(screen.getAllByText('UNKNOWN').length).toBeGreaterThan(0);
  expect(screen.getAllByText('Evidence: No live provider evidence').length).toBeGreaterThan(0);
  expect(screen.queryByText(/healthy/i)).not.toBeInTheDocument();
});

test('resource table supports keyboard selection and opens desired/observed inspector', async () => {
  renderPage();
  await userEvent.click(screen.getByRole('button', { name: 'Resource table' }));
  const resource = screen.getByRole('button', { name: 'FoilTelemetryDb' });
  resource.focus();
  await userEvent.keyboard('{Enter}');
  expect(screen.getByRole('complementary', { name: 'Project resource inspector' })).toHaveTextContent('logical key telemetry_db');
  expect(screen.getByText('No runtime item ID is bound. The logical project key is not substituted for a Fabric item ID.')).toBeInTheDocument();
});

test('staging a dependency creates only a local diff and leaves manifest semantics unchanged', async () => {
  const before = JSON.stringify(ILLUSTRATIVE_FOIL_PROJECT);
  renderPage();
  const inspectButtons = screen.getAllByRole('button', { name: 'Inspect' });
  await userEvent.click(inspectButtons[0]);
  await userEvent.selectOptions(screen.getByLabelText('Dependency target'), 'telemetry_db');
  await userEvent.click(screen.getByRole('button', { name: 'Stage dependency diff' }));
  expect(screen.getByText('resources[eventhouse].dependsOn += "telemetry_db"')).toBeInTheDocument();
  expect(JSON.stringify(ILLUSTRATIVE_FOIL_PROJECT)).toBe(before);
});

test('context changes invalidate inspector selection and local project diffs', async () => {
  const { view } = renderPage();
  await userEvent.click(screen.getAllByRole('button', { name: 'Inspect' })[0]);
  await userEvent.selectOptions(screen.getByLabelText('Dependency target'), 'telemetry_db');
  await userEvent.click(screen.getByRole('button', { name: 'Stage dependency diff' }));
  expect(screen.getByText('Local manifest diff')).toBeInTheDocument();

  view.rerender(
    <ProjectOverviewPage
      project={ILLUSTRATIVE_FOIL_PROJECT}
      profileName="test"
      contextKey="session-a:test"
      onProfileChange={vi.fn()}
    />,
  );
  expect(screen.queryByText('Local manifest diff')).not.toBeInTheDocument();
  expect(screen.getByText('Select a resource from the graph or table.')).toBeInTheDocument();
});

test('drag reorder helper changes presentation order only', () => {
  const semanticSnapshot = JSON.stringify(ILLUSTRATIVE_FOIL_PROJECT);
  expect(reorderLayout(['a', 'b', 'c'], 'c', 'a')).toEqual(['c', 'a', 'b']);
  expect(JSON.stringify(ILLUSTRATIVE_FOIL_PROJECT)).toBe(semanticSnapshot);
});

test('dragging a card persists only browser layout and does not call a network API', () => {
  const fetchSpy = vi.spyOn(globalThis, 'fetch');
  const before = JSON.stringify(ILLUSTRATIVE_FOIL_PROJECT);
  renderPage();
  const cards = screen.getAllByText(/FoilEvents|FoilTelemetryDb/).map((node) => node.closest('[draggable="true"]')).filter(Boolean);
  const source = cards[0] as HTMLElement;
  const target = cards[1] as HTMLElement;
  const dataTransfer = { effectAllowed: 'none', setData: vi.fn(), getData: vi.fn() };
  fireEvent.dragStart(source, { dataTransfer });
  fireEvent.dragOver(target, { dataTransfer });
  fireEvent.drop(target, { dataTransfer });
  expect(JSON.stringify(ILLUSTRATIVE_FOIL_PROJECT)).toBe(before);
  expect(fetchSpy).not.toHaveBeenCalled();
  fetchSpy.mockRestore();
});
