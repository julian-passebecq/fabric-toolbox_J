import {
  Badge,
  Button,
  Card,
  CardHeader,
  Divider,
  Subtitle1,
  Text,
  Title1,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useEffect, useMemo, useState } from 'react';
import type {
  FabricProjectManifest,
  FabricProjectResource,
} from '../data/project-contract.generated';

export type ProjectObservationState = 'matched' | 'drift' | 'missing' | 'denied' | 'unknown';

export type ProjectResourceObservation = {
  key: string;
  state: ProjectObservationState;
  source: string;
  observedAt: string;
  runtimeId?: string;
  detail?: string;
};

type ViewMode = 'flow' | 'dependencies' | 'observed' | 'table';

type ProjectOverviewPageProps = {
  project: FabricProjectManifest;
  profileName: string;
  contextKey: string;
  observations?: ProjectResourceObservation[];
  onProfileChange: (profileName: string) => void;
};

const LAYOUT_KEY_PREFIX = 'fabric-ops-studio.project-layout.v1';

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '20px', marginBottom: '14px', flexWrap: 'wrap' },
  controls: { display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' },
  profileSelect: {
    minWidth: '150px',
    minHeight: '32px',
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorNeutralForeground1,
    padding: '0 8px',
  },
  context: { display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '12px 0' },
  layout: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(280px, 360px)', gap: '18px', marginTop: '18px' },
  graph: { minWidth: 0 },
  nodeGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginTop: '14px' },
  node: { cursor: 'grab', minHeight: '150px' },
  nodeSelected: { outline: `2px solid ${tokens.colorBrandStroke1}`, outlineOffset: '2px' },
  relationList: { display: 'grid', gap: '8px', marginTop: '14px' },
  relation: { padding: '10px 12px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium },
  inspector: { position: 'sticky', top: '0', alignSelf: 'start' },
  inspectorBody: { display: 'grid', gap: '10px' },
  code: { padding: '8px 10px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  muted: { color: tokens.colorNeutralForeground3 },
  warning: { padding: '10px 12px', border: `1px solid ${tokens.colorNeutralStroke2}`, borderRadius: tokens.borderRadiusMedium },
  tableWrap: { overflowX: 'auto', marginTop: '14px' },
  table: { width: '100%', borderCollapse: 'collapse' },
  th: { textAlign: 'left', borderBottom: `1px solid ${tokens.colorNeutralStroke1}`, padding: '8px' },
  td: { borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, padding: '8px', verticalAlign: 'top' },
  diff: { padding: '8px 10px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace' },
  narrowSelect: {
    width: '100%',
    minHeight: '32px',
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorNeutralForeground1,
  },
});

function layoutKey(projectId: string) {
  return `${LAYOUT_KEY_PREFIX}:${projectId}`;
}

function normaliseOrder(project: FabricProjectManifest, stored: string[] | null): string[] {
  const keys = project.resources.map((resource) => resource.key);
  const known = new Set(keys);
  const kept = (stored ?? []).filter((key, index, all) => known.has(key) && all.indexOf(key) === index);
  return [...kept, ...keys.filter((key) => !kept.includes(key))];
}

function readLayout(project: FabricProjectManifest): string[] {
  try {
    const raw = localStorage.getItem(layoutKey(project.projectId));
    const parsed = raw ? JSON.parse(raw) : null;
    return normaliseOrder(project, Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === 'string') : null);
  } catch {
    return normaliseOrder(project, null);
  }
}

export function reorderLayout(order: string[], draggedKey: string, targetKey: string): string[] {
  if (draggedKey === targetKey || !order.includes(draggedKey) || !order.includes(targetKey)) return [...order];
  const next = order.filter((key) => key !== draggedKey);
  const targetIndex = next.indexOf(targetKey);
  next.splice(targetIndex, 0, draggedKey);
  return next;
}

function observationFor(resource: FabricProjectResource, observations: ProjectResourceObservation[]): ProjectResourceObservation {
  return observations.find((item) => item.key === resource.key) ?? {
    key: resource.key,
    state: 'unknown',
    source: 'No live provider evidence',
    observedAt: 'Not observed',
    detail: 'Desired state is known; runtime state has not been queried for this project resource.',
  };
}

function stateLabel(state: ProjectObservationState) {
  if (state === 'matched') return 'MATCHED';
  if (state === 'drift') return 'DRIFT';
  if (state === 'missing') return 'MISSING';
  if (state === 'denied') return 'DENIED';
  return 'UNKNOWN';
}

export function ProjectOverviewPage({
  project,
  profileName,
  contextKey,
  observations = [],
  onProfileChange,
}: ProjectOverviewPageProps) {
  const styles = useStyles();
  const [view, setView] = useState<ViewMode>('flow');
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [order, setOrder] = useState<string[]>(() => readLayout(project));
  const [draggedKey, setDraggedKey] = useState<string | null>(null);
  const [dependencyTarget, setDependencyTarget] = useState('');
  const [pendingDiffs, setPendingDiffs] = useState<string[]>([]);

  useEffect(() => {
    setSelectedKey(null);
    setDependencyTarget('');
    setPendingDiffs([]);
  }, [contextKey]);

  useEffect(() => {
    setOrder(readLayout(project));
  }, [project.projectId]);

  const resourceByKey = useMemo(
    () => new Map(project.resources.map((resource) => [resource.key, resource])),
    [project],
  );
  const orderedResources = useMemo(
    () => normaliseOrder(project, order).map((key) => resourceByKey.get(key)).filter((value): value is FabricProjectResource => Boolean(value)),
    [order, project, resourceByKey],
  );
  const selected = selectedKey ? resourceByKey.get(selectedKey) ?? null : null;
  const selectedObservation = selected ? observationFor(selected, observations) : null;
  const profile = project.profiles[profileName];

  function persistOrder(next: string[]) {
    setOrder(next);
    try {
      localStorage.setItem(layoutKey(project.projectId), JSON.stringify(next));
    } catch {
      // Layout persistence is convenience only; project semantics never depend on it.
    }
  }

  function dropOn(targetKey: string) {
    if (!draggedKey) return;
    persistOrder(reorderLayout(order, draggedKey, targetKey));
    setDraggedKey(null);
  }

  function stageDependencyDiff() {
    if (!selected || !dependencyTarget || dependencyTarget === selected.key || selected.dependsOn.includes(dependencyTarget)) return;
    const diff = `resources[${selected.key}].dependsOn += "${dependencyTarget}"`;
    setPendingDiffs((current) => current.includes(diff) ? current : [...current, diff]);
  }

  const relations = view === 'flow'
    ? project.dataFlows.map((flow) => ({
        key: `${flow.from}:${flow.to}:${flow.kind}`,
        from: flow.from,
        to: flow.to,
        label: flow.kind,
        evidence: flow.evidence,
      }))
    : project.resources.flatMap((resource) => resource.dependsOn.map((dependency) => ({
        key: `${dependency}:${resource.key}:dependency`,
        from: dependency,
        to: resource.key,
        label: 'deploy before',
        evidence: 'manifest',
      })));

  return (
    <>
      <div className={styles.header}>
        <div>
          <Title1>Project</Title1>
          <Text block>{project.displayName}</Text>
          <Text block className={styles.muted}>Desired state from the local project contract. No runtime health is inferred from configuration.</Text>
        </div>
        <div className={styles.controls}>
          <label>
            <Text size={200}>Profile </Text>
            <select
              aria-label="Project profile"
              className={styles.profileSelect}
              value={profileName}
              onChange={(event) => onProfileChange(event.currentTarget.value)}
            >
              {Object.keys(project.profiles).map((name) => <option key={name} value={name}>{name.toUpperCase()}</option>)}
            </select>
          </label>
          <Badge appearance="outline">{project.mode.replace('_', ' ').toUpperCase()}</Badge>
          <Badge appearance="outline">Schema {project.schemaVersion}</Badge>
        </div>
      </div>

      <div className={styles.context}>
        <Badge appearance="outline">Project: {project.projectId}</Badge>
        <Badge appearance="outline">Workspace target: {profile?.workspaceDisplayName ?? 'Unknown profile'}</Badge>
        <Badge appearance="outline">Deployment owner: {profile?.deploymentOwner ?? 'Unknown'}</Badge>
        <Badge appearance="outline">Resources: {project.resources.length}</Badge>
      </div>

      <div className={styles.controls} role="group" aria-label="Project view">
        <Button appearance={view === 'flow' ? 'primary' : 'secondary'} onClick={() => setView('flow')}>Data flow</Button>
        <Button appearance={view === 'dependencies' ? 'primary' : 'secondary'} onClick={() => setView('dependencies')}>Deployment dependencies</Button>
        <Button appearance={view === 'observed' ? 'primary' : 'secondary'} onClick={() => setView('observed')}>Observed / drift</Button>
        <Button appearance={view === 'table' ? 'primary' : 'secondary'} onClick={() => setView('table')}>Resource table</Button>
      </div>

      <div className={styles.layout}>
        <section className={styles.graph} aria-label="Project resource view">
          {view !== 'table' && (
            <>
              <div className={styles.warning}>
                <Text weight="semibold">Layout is presentation only.</Text>
                <Text block size={200}>Drag a card onto another card to reorder this browser layout. Dragging never edits the manifest and never calls Fabric.</Text>
              </div>

              <div className={styles.nodeGrid}>
                {orderedResources.map((resource) => {
                  const observation = observationFor(resource, observations);
                  const isSelected = selectedKey === resource.key;
                  return (
                    <Card
                      key={resource.key}
                      draggable
                      className={isSelected ? `${styles.node} ${styles.nodeSelected}` : styles.node}
                      onDragStart={(event) => {
                        setDraggedKey(resource.key);
                        event.dataTransfer.effectAllowed = 'move';
                        event.dataTransfer.setData('text/plain', resource.key);
                      }}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={(event) => {
                        event.preventDefault();
                        dropOn(resource.key);
                      }}
                    >
                      <CardHeader
                        header={<Subtitle1>{resource.displayName}</Subtitle1>}
                        description={<Text>{resource.type} · {resource.key}</Text>}
                        action={<Button size="small" appearance={isSelected ? 'primary' : 'secondary'} onClick={() => setSelectedKey(resource.key)}>Inspect</Button>}
                      />
                      <Text block size={200}>Desired: {resource.management.toUpperCase()}</Text>
                      {view === 'observed' ? (
                        <>
                          <Badge appearance="outline">{stateLabel(observation.state)}</Badge>
                          <Text block size={200}>Evidence: {observation.source}</Text>
                          <Text block size={200}>Observed: {observation.observedAt}</Text>
                        </>
                      ) : (
                        <Text block size={200} className={styles.muted}>{resource.definitionPath}</Text>
                      )}
                    </Card>
                  );
                })}
              </div>

              {view !== 'observed' && (
                <div className={styles.relationList} aria-label={view === 'flow' ? 'Declared data flows' : 'Deployment dependency edges'}>
                  <Subtitle1>{view === 'flow' ? 'Declared data-flow edges' : 'Deployment dependency edges'}</Subtitle1>
                  {relations.length === 0 && <Text className={styles.muted}>No relationships declared.</Text>}
                  {relations.map((relation) => (
                    <div key={relation.key} className={styles.relation}>
                      <Text weight="semibold">{resourceByKey.get(relation.from)?.displayName ?? relation.from}</Text>
                      <Text> → {relation.label} → </Text>
                      <Text weight="semibold">{resourceByKey.get(relation.to)?.displayName ?? relation.to}</Text>
                      <Text block size={200} className={styles.muted}>Evidence: {relation.evidence}</Text>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {view === 'table' && (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th className={styles.th}>Resource</th>
                    <th className={styles.th}>Type</th>
                    <th className={styles.th}>Desired</th>
                    <th className={styles.th}>Observed</th>
                    <th className={styles.th}>Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {project.resources.map((resource) => {
                    const observation = observationFor(resource, observations);
                    return (
                      <tr key={resource.key}>
                        <td className={styles.td}><Button appearance="subtle" onClick={() => setSelectedKey(resource.key)}>{resource.displayName}</Button></td>
                        <td className={styles.td}>{resource.type}</td>
                        <td className={styles.td}>{resource.management}</td>
                        <td className={styles.td}>{stateLabel(observation.state)}</td>
                        <td className={styles.td}>{observation.source} · {observation.observedAt}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside className={styles.inspector} aria-label="Project resource inspector">
          <Card>
            <CardHeader header={<Subtitle1>{selected ? selected.displayName : 'Resource inspector'}</Subtitle1>} description={<Text>{selected ? `${selected.type} · logical key ${selected.key}` : 'Select a resource from the graph or table.'}</Text>} />
            {selected && selectedObservation && (
              <div className={styles.inspectorBody}>
                <Divider />
                <Text weight="semibold">Desired state</Text>
                <code className={styles.code}>{selected.definitionPath}</code>
                <Text size={200}>Management: {selected.management}</Text>
                <Text size={200}>Deploy after: {selected.dependsOn.length ? selected.dependsOn.join(', ') : 'none'}</Text>

                <Text weight="semibold">Observed state</Text>
                <Badge appearance="outline">{stateLabel(selectedObservation.state)}</Badge>
                <Text size={200}>Evidence source: {selectedObservation.source}</Text>
                <Text size={200}>Observed at: {selectedObservation.observedAt}</Text>
                <Text size={200}>{selectedObservation.detail ?? 'No additional evidence.'}</Text>
                {!selectedObservation.runtimeId && <Text size={200} className={styles.muted}>No runtime item ID is bound. The logical project key is not substituted for a Fabric item ID.</Text>}

                <Text weight="semibold">Local relationship proposal</Text>
                <select
                  aria-label="Dependency target"
                  className={styles.narrowSelect}
                  value={dependencyTarget}
                  onChange={(event) => setDependencyTarget(event.currentTarget.value)}
                >
                  <option value="">Choose resource</option>
                  {project.resources.filter((resource) => resource.key !== selected.key && !selected.dependsOn.includes(resource.key)).map((resource) => (
                    <option key={resource.key} value={resource.key}>{resource.displayName}</option>
                  ))}
                </select>
                <Button disabled={!dependencyTarget} onClick={stageDependencyDiff}>Stage dependency diff</Button>
                <Text size={200} className={styles.muted}>This stages a local manifest proposal only. It does not mutate the loaded project or Fabric.</Text>
              </div>
            )}
          </Card>

          {pendingDiffs.length > 0 && (
            <Card style={{ marginTop: '12px' }}>
              <CardHeader header={<Subtitle1>Local manifest diff</Subtitle1>} description={<Text>Unapplied project edits</Text>} />
              {pendingDiffs.map((diff) => <div key={diff} className={styles.diff}>{diff}</div>)}
              <Button size="small" appearance="secondary" onClick={() => setPendingDiffs([])}>Discard local diffs</Button>
            </Card>
          )}
        </aside>
      </div>
    </>
  );
}
