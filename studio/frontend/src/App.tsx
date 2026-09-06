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
import { useEffect, useMemo, useState } from 'react';
import { Capability, connectFabric, getCapabilities, getSession } from './api/client';
import { CommandWorkbench } from './components/CommandWorkbench';
import staticCapabilities from './data/capabilities.json';
import { ActivityPage } from './pages/ActivityPage';
import { DiagnosticsPage } from './pages/DiagnosticsPage';
import { InventoryPage } from './pages/InventoryPage';
import { OperationsPage } from './pages/OperationsPage';
import { SourcesPage } from './pages/SourcesPage';
import { SpecializedToolsPage } from './pages/SpecializedToolsPage';

const nav = [
  ['Overview', AppsList24Regular],
  ['Workspaces', BuildingFactory24Regular],
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
  connectionBar: { display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 20px', backgroundColor: tokens.colorNeutralBackground1, borderBottom: `1px solid ${tokens.colorNeutralStroke2}` },
  tenantInput: { width: '360px' },
  connectionText: { marginLeft: '4px', color: tokens.colorNeutralForeground3 },
  body: { display: 'grid', gridTemplateColumns: '240px 1fr', minHeight: 0 },
  nav: { backgroundColor: tokens.colorNeutralBackground1, borderRight: `1px solid ${tokens.colorNeutralStroke2}`, padding: '12px 8px' },
  navButton: { width: '100%', justifyContent: 'flex-start', marginBottom: '4px' },
  main: { padding: '24px', overflow: 'auto' },
  hero: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', gap: '24px' },
  cards: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: '14px', marginTop: '16px' },
  stats: { display: 'grid', gridTemplateColumns: 'repeat(4, minmax(120px, 1fr))', gap: '12px', margin: '20px 0 28px' },
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
  return capability.risk === 'read' && (capability.provider === 'MicrosoftFabricMgmt' || capability.provider === 'Fabric REST API');
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

  const categories = useMemo(() => new Set(catalog.map((item) => item.category)).size, [catalog]);
  const workspaceCapability = catalog.find((item) => item.id === 'ps-workspace-get-fabricworkspace');
  const workspaceAccessCapabilities = catalog.filter((item) => item.id === 'ps-workspace-get-fabricworkspaceroleassignment');
  const capacityCapability = catalog.find((item) => item.id === 'ps-capacity-get-fabriccapacity');
  const connectionCapability = catalog.find((item) => item.id === 'ps-connections-get-fabricconnection');
  const itemCapabilities = catalog.filter((item) => ['rest-items-list', 'rest-item-get', 'rest-item-connections-list'].includes(item.id));
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

  async function handleConnect() {
    if (!tenantId.trim()) return;
    setConnecting(true);
    setConnected(false);
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
                {cap.response_mode === 'fabric-lro' && <Badge appearance="tint">FABRIC LRO</Badge>}
                {cap.generated && <Badge appearance="ghost">AUTO-DISCOVERED</Badge>}
              </div>
              <Text block size={200}>Source: {cap.source}</Text>
              {cap.command && <code className={styles.code}>{cap.command}</code>}
              {cap.endpoint && <code className={styles.code}>{cap.endpoint}</code>}
              <div className={styles.sourceRow}>
                <Button size="small" onClick={() => setSelected(cap)}>{isReadExecutable(cap) ? 'Open / run' : 'Inspect'}</Button>
                {(cap.command || cap.endpoint) && <Button size="small" appearance="secondary" onClick={() => copyCommand(cap)}>Copy</Button>}
              </div>
            </Card>
          ))}
        </div>
        {selected && <CommandWorkbench capability={selected} connected={connected} onClose={() => setSelected(null)} />}
      </>
    );
  }

  function renderOverview() {
    return (
      <>
        <div className={styles.hero}>
          <div>
            <Title1>Overview</Title1>
            <Text block>Operational control plane for Microsoft Fabric.</Text>
          </div>
        </div>
        <div className={styles.stats}>
          {[['Catalog capabilities', String(catalog.length)], ['Capability groups', String(categories)], ['Execution mode', 'Read only'], ['Fabric session', connected ? 'Connected' : 'Offline']].map(([label, value]) => (
            <Card key={label} className={styles.stat}>
              <Subtitle1>{value}</Subtitle1>
              <Text>{label}</Text>
            </Card>
          ))}
        </div>
        <div className={styles.cards}>
          <Card><CardHeader header={<Subtitle1>Workspace inventory</Subtitle1>} description="Inventory workspaces and inspect role assignments through the upstream module." /><Button onClick={() => setSection('Workspaces')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Items</Subtitle1>} description="List items, retrieve item details and inspect item connections through official Fabric APIs." /><Button onClick={() => setSection('Items')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Runs & schedules</Subtitle1>} description="Inspect item job instances and schedules through the official Job Scheduler API." /><Button onClick={() => setSection('Runs & Schedules')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Capacity inventory</Subtitle1>} description="Inspect Fabric capacities without changing state." /><Button onClick={() => setSection('Capacities')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Connection inventory</Subtitle1>} description="Run Get-FabricConnection through the upstream module." /><Button onClick={() => setSection('Connections')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Deployment & Git</Subtitle1>} description="Inspect deployment pipelines, Git connections and LRO-aware workspace Git status." /><Button onClick={() => setSection('Deployment & Git')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Security</Subtitle1>} description="Inspect the upstream Fabric Security Audit workflow, prerequisites and entrypoint." /><Button onClick={() => setSection('Security')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Assessment</Subtitle1>} description="Expose the upstream migration assessment workflow without reimplementing its CLI." /><Button onClick={() => setSection('Assessment')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Diagnostics</Subtitle1>} description="Check PowerShell, upstream modules, Azure CLI and specialized-tool readiness." /><Button onClick={() => setSection('Diagnostics')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>Sources</Subtitle1>} description="See exactly which repo/module/API provides each capability." /><Button onClick={() => setSection('Sources')}>Open</Button></Card>
          <Card><CardHeader header={<Subtitle1>PowerShell Library</Subtitle1>} description="Browse and preview commands by Fabric resource and upstream source." /><Button onClick={() => setSection('PowerShell Library')}>Open library</Button></Card>
        </div>
      </>
    );
  }

  function renderSection() {
    if (section === 'Workspaces') {
      return (
        <>
          <InventoryPage title="Workspaces" description="Live workspace inventory from the upstream MicrosoftFabricMgmt PowerShell module." connected={connected} capability={workspaceCapability} fields={[{ key: 'id', label: 'ID' }, { key: 'description', label: 'Description' }, { key: 'capacityId', label: 'Capacity ID' }, { key: 'CapacityName', label: 'Capacity' }]} />
          <div className={styles.sectionSpacer}>
            <OperationsPage title="Workspace access" description="Read-only workspace role-assignment inspection. Parameter forms and source paths are generated from the upstream MicrosoftFabricMgmt cmdlet." capabilities={workspaceAccessCapabilities} connected={connected} />
          </div>
        </>
      );
    }
    if (section === 'Items') {
      return <OperationsPage title="Items" description="Generic Fabric item inventory, item detail and item-connection reads sourced from official Items REST APIs. Requests are executed through the upstream MicrosoftFabricMgmt API helper." capabilities={itemCapabilities} connected={connected} />;
    }
    if (section === 'Runs & Schedules') {
      return <OperationsPage title="Runs & Schedules" description="Read-only Job Scheduler operations from the official Fabric REST API. Job execution, cancellation and schedule writes remain disabled." capabilities={jobCapabilities} connected={connected} />;
    }
    if (section === 'Capacities') {
      return <InventoryPage title="Capacities" description="Live Fabric capacity inventory from the upstream MicrosoftFabricMgmt PowerShell module." connected={connected} capability={capacityCapability} fields={[{ key: 'id', label: 'ID' }, { key: 'sku', label: 'SKU' }, { key: 'region', label: 'Region' }, { key: 'state', label: 'State' }]} />;
    }
    if (section === 'Connections') {
      return <InventoryPage title="Connections" description="Live connection inventory from the upstream MicrosoftFabricMgmt Get-FabricConnection cmdlet. Fields are discovered from returned data so upstream additions remain visible without UI rewrites." connected={connected} capability={connectionCapability} />;
    }
    if (section === 'Deployment & Git') {
      return <OperationsPage title="Deployment & Git" description="Read-only deployment-pipeline and Git operations. Git status uses Fabric's long-running-operation protocol through MicrosoftFabricMgmt -WaitForCompletion rather than a Studio-owned poller." capabilities={deploymentCapabilities} connected={connected} />;
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
          <Badge appearance="outline">READ ONLY</Badge>
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
      </div>

      <div className={styles.body}>
        <nav className={styles.nav}>
          {nav.map(([label, Icon]) => (
            <Button key={label} className={styles.navButton} appearance={section === label ? 'primary' : 'subtle'} icon={<Icon />} onClick={() => { setSection(label); setSelected(null); }}>
              {label}
            </Button>
          ))}
        </nav>
        <main className={styles.main}>{renderSection()}</main>
      </div>
    </div>
  );
}
