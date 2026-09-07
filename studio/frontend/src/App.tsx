import {
  Badge,
  Button,
  Card,
  CardHeader,
  Divider,
  Input,
  Spinner,
  Subtitle1,
  Text,
  Title1,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import {
  AppsList24Regular,
  BuildingFactory24Regular,
  CloudDatabaseRegular,
  DataUsageSettings24Regular,
  History24Regular,
  Key24Regular,
  Library24Regular,
  PlugConnected24Regular,
  Shield24Regular,
  Timeline24Regular,
  Wrench24Regular,
} from '@fluentui/react-icons';
import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Capability, connectFabric, getCapabilities, getSession } from './api/client';
import { CommandWorkbench } from './components/CommandWorkbench';
import staticCapabilities from './data/capabilities.json';
import { InventoryPage } from './pages/InventoryPage';
import { OperationsPage } from './pages/OperationsPage';
import type { ItemContext } from './pages/ItemExplorerPage';

const ActivityPage = lazy(() => import('./pages/ActivityPage').then((module) => ({ default: module.ActivityPage })));
const ChangePlansPage = lazy(() => import('./pages/ChangePlansPage').then((module) => ({ default: module.ChangePlansPage })));
const DiagnosticsPage = lazy(() => import('./pages/DiagnosticsPage').then((module) => ({ default: module.DiagnosticsPage })));
const ItemExplorerPage = lazy(() => import('./pages/ItemExplorerPage').then((module) => ({ default: module.ItemExplorerPage })));
const SourcesPage = lazy(() => import('./pages/SourcesPage').then((module) => ({ default: module.SourcesPage })));
const SpecializedToolsPage = lazy(() => import('./pages/SpecializedToolsPage').then((module) => ({ default: module.SpecializedToolsPage })));

type WorkspaceContext = { id: string; name: string };

const nav = [
  ['Overview', AppsList24Regular],
  ['Workspaces', BuildingFactory24Regular],
  ['Change Plans', Shield24Regular],
  ['Items', CloudDatabaseRegular],
  ['Runs & Schedules', Timeline24Regular],
  ['Capacities', DataUsageSettings24Regular],
  ['Connections', PlugConnected24Regular],
  ['Deployment & Git', History24Regular],
  ['Security', Shield24Regular],
  ['Assessment', Wrench24Regular],
  ['Lineage', Timeline24Regular],
  ['PowerShell Library', Library24Regular],
  ['Diagnostics', Wrench24Regular],
  ['Activity Log', History24Regular],
  ['Sources', Key24Regular],
] as const;

const useStyles = makeStyles({
  root: { minHeight: '100vh', display: 'grid', gridTemplateRows: '64px 48px 1fr', backgroundColor: tokens.colorNeutralBackground2 },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', backgroundColor: tokens.colorNeutralBackground1, borderBottom: `1px solid ${tokens.colorNeutralStroke2}` },
  connectionBar: { display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 20px', backgroundColor: tokens.colorNeutralBackground1, borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, overflowX: 'auto' },
  tenantInput: { width: '330px', minWidth: '250px' },
  connectionText: { marginLeft: '4px', color: tokens.colorNeutralForeground3, whiteSpace: 'nowrap' },
  body: { display: 'grid', gridTemplateColumns: '240px 1fr', minHeight: 0 },
  nav: { backgroundColor: tokens.colorNeutralBackground1, borderRight: `1px solid ${tokens.colorNeutralStroke2}`, padding: '12px 8px' },
  navButton: { width: '100%', justifyContent: 'flex-start', marginBottom: '4px' },
  main: { padding: '24px', overflow: 'auto' },
  hero: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', gap: '24px' },
  cards: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: '14px', marginTop: '16px' },
  stats: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(145px, 1fr))', gap: '12px', margin: '20px 0 28px' },
  stat: { padding: '16px' },
  sourceRow: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginTop: '8px' },
  search: { width: '340px' },
  code: { display: 'block', padding: '10px 12px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  muted: { color: tokens.colorNeutralForeground3 },
  sectionSpacer: { marginTop: '36px', paddingTop: '28px', borderTop: `1px solid ${tokens.colorNeutralStroke2}` },
});

function riskAppearance(risk: Capability['risk']) {
  return risk === 'read' ? 'tint' : risk === 'destructive' ? 'filled' : 'outline';
}

function isReadExecutable(capability: Capability) {
  return capability.risk === 'read'
    && capability.execution_policy !== 'blocked'
    && (capability.provider === 'MicrosoftFabricMgmt' || capability.provider === 'Fabric REST API');
}

function isGuardedWrite(capability: Capability) {
  return capability.risk === 'write'
    && capability.execution_policy === 'guarded-write'
    && capability.provider === 'MicrosoftFabricMgmt';
}

function rowValue(row: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = row[key];
    if (value !== null && value !== undefined && value !== '') return String(value);
  }
  return '';
}

export function App() {
  const styles = useStyles();
  const [section, setSection] = useState('Overview');
  const [query, setQuery] = useState('');
  const [catalog, setCatalog] = useState<Capability[]>(staticCapabilities as Capability[]);
  const [catalogState, setCatalogState] = useState<'loading' | 'live' | 'fallback'>('loading');
  const [selected, setSelected] = useState<Capability | null>(null);
  const [tenantId, setTenantId] = useState('');
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [connectionText, setConnectionText] = useState('Not connected');
  const [workspaceContext, setWorkspaceContext] = useState<WorkspaceContext | null>(null);
  const [itemContext, setItemContext] = useState<ItemContext | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCapabilities()
      .then((items) => {
        if (!cancelled) {
          setCatalog(items);
          setCatalogState('live');
        }
      })
      .catch(() => {
        if (!cancelled) setCatalogState('fallback');
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    getSession()
      .then((session) => {
        if (cancelled) return;
        setConnected(session.connected);
        if (session.tenant_id) setTenantId(session.tenant_id);
        setConnectionText(session.connected
          ? `Connected to tenant ${session.tenant_id ?? 'current session'}`
          : 'Not connected');
      })
      .catch(() => {
        if (!cancelled) setConnectionText('Backend session unavailable');
      });
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return catalog.filter((cap) => !q || `${cap.title} ${cap.category} ${cap.provider} ${cap.command ?? ''} ${cap.endpoint ?? ''} ${cap.source_path ?? ''}`.toLowerCase().includes(q));
  }, [catalog, query]);

  const workspaceDefaults: Record<string, string | boolean> = {};
  if (workspaceContext) {
    workspaceDefaults.workspaceId = workspaceContext.id;
    workspaceDefaults.WorkspaceId = workspaceContext.id;
  }

  const itemDefaults: Record<string, string | boolean> = { ...workspaceDefaults };
  if (itemContext) {
    itemDefaults.itemId = itemContext.id;
    itemDefaults.ItemId = itemContext.id;
  }

  const categories = useMemo(() => new Set(catalog.map((item) => item.category)).size, [catalog]);
  const guardedWriteCount = useMemo(() => catalog.filter(isGuardedWrite).length, [catalog]);
  const workspaceCapability = catalog.find((item) => item.id === 'ps-workspace-get-fabricworkspace');
  const workspaceAccessCapabilities = catalog.filter((item) => item.id === 'ps-workspace-get-fabricworkspaceroleassignment');
  const workspaceWriteCapabilities = catalog.filter((item) => ['ps-workspace-new-fabricworkspace', 'ps-workspace-update-fabricworkspace'].includes(item.id));
  const capacityCapability = catalog.find((item) => item.id === 'ps-capacity-get-fabriccapacity');
  const connectionCapability = catalog.find((item) => item.id === 'ps-connections-get-fabricconnection');
  const jobCapabilities = catalog.filter((item) => ['rest-job-instances-list', 'rest-schedules-list'].includes(item.id));
  const deploymentCapabilities = catalog.filter((item) => item.id === 'rest-git-status' || [
    'Get-FabricDeploymentPipeline',
    'Get-FabricDeploymentPipelineStage',
    'Get-FabricDeploymentPipelineOperation',
    'Get-FabricWorkspaceGitConnection',
  ].includes(item.command ?? ''));

  async function copyCommand(cap: Capability) {
    const value = cap.command ?? cap.endpoint;
    if (!value) return;
    await navigator.clipboard.writeText(value);
  }

  function selectWorkspace(row: Record<string, unknown>) {
    const id = rowValue(row, ['id', 'Id', 'workspaceId', 'WorkspaceId']);
    if (!id) return;
    const name = rowValue(row, ['displayName', 'DisplayName', 'name', 'Name']) || id;
    if (workspaceContext?.id !== id) setItemContext(null);
    setWorkspaceContext({ id, name });
  }

  async function handleConnect() {
    if (!tenantId.trim()) return;
    setConnecting(true);
    setConnected(false);
    setWorkspaceContext(null);
    setItemContext(null);
    setConnectionText('Opening Fabric authentication...');
    try {
      const result = await connectFabric(tenantId.trim());
      if (result.success === false) throw new Error(String(result.error ?? 'Authentication failed'));
      setConnected(true);
      setConnectionText(`Connected to tenant ${tenantId.trim()}`);
    } catch (err) {
      setConnectionText(err instanceof Error ? err.message : String(err));
    } finally {
      setConnecting(false);
    }
  }

  function renderLibrary() {
    return (
      <>
        <div className={styles.hero}>
          <div>
            <Title1>PowerShell Library</Title1>
            <Text block>Search upstream Fabric management cmdlets and registered official REST operations, inspect their source, and preview the exact PowerShell execution.</Text>
            <Text block className={styles.muted}>{catalog.length} capabilities across {categories} categories.</Text>
          </div>
          <Input className={styles.search} placeholder="Search command, endpoint, category, provider or path" value={query} onChange={(_, data) => setQuery(data.value)} />
        </div>
        <Divider />
        {catalogState === 'loading' && <Spinner label="Discovering PowerShell capabilities" />}
        <div className={styles.cards}>
          {filtered.map((cap) => (
            <Card key={cap.id}>
              <CardHeader header={<Subtitle1>{cap.title}</Subtitle1>} description={<Text>{cap.description}</Text>} />
              <div className={styles.sourceRow}>
                <Badge appearance="outline">{cap.category}</Badge>
                <Badge appearance="outline">{cap.provider}</Badge>
                <Badge appearance={riskAppearance(cap.risk)}>{cap.risk.toUpperCase()}</Badge>
                {cap.execution_policy && <Badge appearance="outline">{cap.execution_policy.toUpperCase()}</Badge>}
                {cap.supports_whatif && <Badge appearance="tint">WHATIF</Badge>}
                {cap.response_mode === 'fabric-lro' && <Badge appearance="tint">FABRIC LRO</Badge>}
                {cap.generated && <Badge appearance="ghost">AUTO-DISCOVERED</Badge>}
              </div>
              <Text block size={200}>Source: {cap.source}</Text>
              {cap.command && <code className={styles.code}>{cap.command}</code>}
              {cap.endpoint && <code className={styles.code}>{cap.endpoint}</code>}
              <div className={styles.sourceRow}>
                <Button size="small" onClick={() => setSelected(cap)}>
                  {isReadExecutable(cap) ? 'Open / run' : isGuardedWrite(cap) ? 'Plan / apply' : 'Inspect'}
                </Button>
                {(cap.command || cap.endpoint) && <Button size="small" appearance="secondary" onClick={() => copyCommand(cap)}>Copy</Button>}
              </div>
            </Card>
          ))}
        </div>
        {selected && <CommandWorkbench capability={selected} connected={connected} defaultParameters={itemContext ? itemDefaults : workspaceDefaults} onClose={() => setSelected(null)} />}
      </>
    );
  }

  function renderOverview() {
    return (
      <>
        <div className={styles.hero}>
          <div>
            <Title1>Overview</Title1>
            <Text block>Operational control plane for Microsoft Fabric with read execution and tightly allowlisted guarded writes.</Text>
          </div>
        </div>
        <div className={styles.stats}>
          {[
            ['Catalog capabilities', String(catalog.length)],
            ['Guarded writes', String(guardedWriteCount)],
            ['Execution mode', 'Read + guarded'],
            ['Workspace context', workspaceContext?.name ?? 'None'],
            ['Item context', itemContext?.name ?? 'None'],
          ].map(([label, value]) => (
            <Card key={label} className={styles.stat}>
              <Subtitle1>{value}</Subtitle1>
              <Text>{label}</Text>
            </Card>
          ))}
        </div>
        <div className={styles.cards}>
          <Card><CardHeader header={<Subtitle1>Workspace inventory & changes</Subtitle1>} description="Inventory workspaces and use guarded plans for the explicitly allowlisted create/update operations." /><Button onClick={() => setSection('Workspaces')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Change Plans</Subtitle1>} description="Review tenant-bound, expiring, single-use mutation plans created in the current backend session." /><Button onClick={() => setSection('Change Plans')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Item explorer</Subtitle1>} description="Select an item once and inherit its workspace/item IDs across detail, connection, job and schedule operations." /><Button onClick={() => setSection('Items')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Runs & schedules</Subtitle1>} description="Inspect item job instances and schedules with selected workspace/item context prefilled." /><Button onClick={() => setSection('Runs & Schedules')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Capacity inventory</Subtitle1>} description="Inspect Fabric capacities without changing state." /><Button onClick={() => setSection('Capacities')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Connection inventory</Subtitle1>} description="Run Get-FabricConnection through the upstream module." /><Button onClick={() => setSection('Connections')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Deployment & Git</Subtitle1>} description="Inspect deployment pipelines, Git connections and LRO-aware workspace Git status." /><Button onClick={() => setSection('Deployment & Git')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Security</Subtitle1>} description="Inspect the upstream Fabric Security Audit workflow, prerequisites and entrypoint." /><Button onClick={() => setSection('Security')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Assessment</Subtitle1>} description="Expose the upstream migration assessment workflow without reimplementing its CLI." /><Button onClick={() => setSection('Assessment')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Diagnostics</Subtitle1>} description="Check PowerShell, upstream modules, Azure CLI and specialized-tool readiness." /><Button onClick={() => setSection('Diagnostics')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Sources</Subtitle1>} description="See exactly which repo/module/API provides each capability." /><Button onClick={() => setSection('Sources')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>PowerShell Library</Subtitle1>} description="Browse commands, execution policies and upstream provenance." /><Button onClick={() => setSection('PowerShell Library')}>Open library</Button></Card>
        </div>
      </>
    );
  }

  function renderSection() {
    if (section === 'Workspaces') {
      return (
        <>
          <InventoryPage
            title="Workspaces"
            description="Live workspace inventory from the upstream MicrosoftFabricMgmt PowerShell module. Select one workspace to reuse its ID across Studio operation forms."
            connected={connected}
            capability={workspaceCapability}
            fields={[{ key: 'id', label: 'ID' }, { key: 'description', label: 'Description' }, { key: 'capacityId', label: 'Capacity ID' }, { key: 'CapacityName', label: 'Capacity' }]}
            selectedRowId={workspaceContext?.id}
            selectLabel="Use workspace"
            recentScope="workspaces"
            onSelectRow={selectWorkspace}
          />
          <div className={styles.sectionSpacer}>
            <OperationsPage
              title="Guarded workspace changes"
              description="Only create workspace and update workspace metadata are enabled. Both use upstream SupportsShouldProcess/-WhatIf plus Studio's tenant-bound, expiring, typed-approval mutation broker."
              capabilities={workspaceWriteCapabilities}
              connected={connected}
              defaultParameters={workspaceDefaults}
            />
          </div>
          <div className={styles.sectionSpacer}>
            <OperationsPage title="Workspace access" description="Read-only workspace role-assignment inspection. Role mutations remain blocked in this milestone." capabilities={workspaceAccessCapabilities} connected={connected} defaultParameters={workspaceDefaults} />
          </div>
        </>
      );
    }
    if (section === 'Change Plans') return <ChangePlansPage />;
    if (section === 'Items') {
      return (
        <ItemExplorerPage
          connected={connected}
          workspaceContext={workspaceContext}
          itemContext={itemContext}
          catalog={catalog}
          onSelectItem={setItemContext}
          onClearItem={() => setItemContext(null)}
          onOpenRuns={() => setSection('Runs & Schedules')}
        />
      );
    }
    if (section === 'Runs & Schedules') {
      return <OperationsPage title="Runs & Schedules" description="Read-only Job Scheduler operations from the official Fabric REST API. Selected workspace/item context is prefilled automatically; job execution, cancellation and schedule writes remain disabled." capabilities={jobCapabilities} connected={connected} defaultParameters={itemDefaults} />;
    }
    if (section === 'Capacities') {
      return <InventoryPage title="Capacities" description="Live Fabric capacity inventory from the upstream MicrosoftFabricMgmt PowerShell module." connected={connected} capability={capacityCapability} fields={[{ key: 'id', label: 'ID' }, { key: 'sku', label: 'SKU' }, { key: 'region', label: 'Region' }, { key: 'state', label: 'State' }]} />;
    }
    if (section === 'Connections') {
      return <InventoryPage title="Connections" description="Live connection inventory from the upstream MicrosoftFabricMgmt Get-FabricConnection cmdlet. Fields are discovered from returned data so upstream additions remain visible without UI rewrites." connected={connected} capability={connectionCapability} />;
    }
    if (section === 'Deployment & Git') {
      return <OperationsPage title="Deployment & Git" description="Read-only deployment-pipeline and Git operations. Git status uses Fabric's long-running-operation protocol through MicrosoftFabricMgmt -WaitForCompletion rather than a Studio-owned poller." capabilities={deploymentCapabilities} connected={connected} defaultParameters={workspaceDefaults} />;
    }
    if (section === 'Security') {
      return <SpecializedToolsPage category="Security" description="Security troubleshooting remains an upstream specialized workflow because it crosses Fabric, Graph and SQL permission layers and emits a report bundle." />;
    }
    if (section === 'Assessment') {
      return <SpecializedToolsPage category="Assessment" description="Migration assessment remains the upstream fat CLI with its own Python package, authentication and extraction lifecycle." />;
    }
    if (section === 'Lineage') {
      return <SpecializedToolsPage category="Lineage" description="Column-level lineage is exposed as the upstream Fabric notebook workflow rather than being copied into Studio." />;
    }
    if (section === 'PowerShell Library') return renderLibrary();
    if (section === 'Diagnostics') return <DiagnosticsPage />;
    if (section === 'Sources') return <SourcesPage />;
    if (section === 'Activity Log') return <ActivityPage />;
    if (section === 'Overview') return renderOverview();
    return <Card><CardHeader header={<Subtitle1>{section} module</Subtitle1>} description="This module will be connected to upstream providers without duplicating their implementation." /></Card>;
  }

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div>
          <Title1>Fabric Ops Studio</Title1>
          <Text size={200}>Management, operations and PowerShell</Text>
        </div>
        <div className={styles.sourceRow}>
          <Badge appearance="outline">READ EXECUTION</Badge>
          <Badge appearance="tint">{guardedWriteCount} GUARDED WRITES</Badge>
          <Badge appearance="filled">Provenance enabled</Badge>
          <Badge appearance="outline">Catalog: {catalogState}</Badge>
        </div>
      </header>

      <div className={styles.connectionBar}>
        <Text weight="semibold">Tenant</Text>
        <Input className={styles.tenantInput} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" value={tenantId} onChange={(_, data) => setTenantId(data.value)} />
        <Button appearance="primary" disabled={connecting || !tenantId.trim()} onClick={handleConnect}>{connecting ? 'Connecting…' : 'Connect'}</Button>
        <Badge appearance={connected ? 'tint' : 'outline'}>{connected ? 'CONNECTED' : 'OFFLINE'}</Badge>
        <Text size={200} className={styles.connectionText}>{connectionText}</Text>
        {workspaceContext && <Badge appearance="tint">Workspace: {workspaceContext.name}</Badge>}
        {itemContext && <Badge appearance="tint">Item: {itemContext.name}</Badge>}
        {itemContext && <Button size="small" appearance="subtle" onClick={() => setItemContext(null)}>Clear item</Button>}
        {workspaceContext && <Button size="small" appearance="subtle" onClick={() => { setWorkspaceContext(null); setItemContext(null); }}>Clear workspace</Button>}
      </div>

      <div className={styles.body}>
        <nav className={styles.nav}>
          {nav.map(([label, Icon]) => (
            <Button key={label} className={styles.navButton} appearance={section === label ? 'primary' : 'subtle'} icon={<Icon />} onClick={() => { setSection(label); setSelected(null); }}>
              {label}
            </Button>
          ))}
        </nav>
        <main className={styles.main}>
          <Suspense fallback={<Spinner label="Loading Studio module" />}>
            {renderSection()}
          </Suspense>
        </main>
      </div>
    </div>
  );
}
