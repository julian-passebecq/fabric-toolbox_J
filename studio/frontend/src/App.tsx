import {
  Badge,
  Button,
  Card,
  CardHeader,
  Divider,
  Input,
  Subtitle1,
  Text,
  Title1,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import {
  AppsList24Regular,
  BuildingFactory24Regular,
  CloudDatabase24Regular,
  DataUsageSettings24Regular,
  History24Regular,
  Key24Regular,
  Library24Regular,
  PlugConnected24Regular,
  Shield24Regular,
  Timeline24Regular,
  Wrench24Regular,
} from '@fluentui/react-icons';
import { useMemo, useState } from 'react';
import capabilities from './data/capabilities.json';

type Capability = {
  id: string;
  title: string;
  category: string;
  provider: string;
  source: string;
  risk: 'read' | 'write' | 'admin' | 'destructive';
  command?: string;
  endpoint?: string;
  description: string;
};

const nav = [
  ['Overview', AppsList24Regular],
  ['Workspaces', BuildingFactory24Regular],
  ['Items', CloudDatabase24Regular],
  ['Runs & Schedules', Timeline24Regular],
  ['Capacities', DataUsageSettings24Regular],
  ['Connections', PlugConnected24Regular],
  ['Deployment & Git', History24Regular],
  ['Security', Shield24Regular],
  ['Assessment', Wrench24Regular],
  ['Lineage', Timeline24Regular],
  ['PowerShell Library', Library24Regular],
  ['Activity Log', History24Regular],
  ['Sources', Key24Regular],
] as const;

const useStyles = makeStyles({
  root: { minHeight: '100vh', display: 'grid', gridTemplateRows: '56px 1fr', backgroundColor: tokens.colorNeutralBackground2 },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', backgroundColor: tokens.colorNeutralBackground1, borderBottom: `1px solid ${tokens.colorNeutralStroke2}` },
  body: { display: 'grid', gridTemplateColumns: '240px 1fr', minHeight: 0 },
  nav: { backgroundColor: tokens.colorNeutralBackground1, borderRight: `1px solid ${tokens.colorNeutralStroke2}`, padding: '12px 8px' },
  navButton: { width: '100%', justifyContent: 'flex-start', marginBottom: '4px' },
  main: { padding: '24px', overflow: 'auto' },
  hero: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', gap: '24px' },
  cards: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '14px', marginTop: '16px' },
  stats: { display: 'grid', gridTemplateColumns: 'repeat(4, minmax(120px, 1fr))', gap: '12px', margin: '20px 0 28px' },
  stat: { padding: '16px' },
  sourceRow: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginTop: '8px' },
  search: { width: '320px' },
});

export function App() {
  const styles = useStyles();
  const [section, setSection] = useState('Overview');
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (capabilities as Capability[]).filter((cap) => !q || `${cap.title} ${cap.category} ${cap.provider} ${cap.command ?? ''}`.toLowerCase().includes(q));
  }, [query]);

  const showLibrary = section === 'PowerShell Library' || section === 'Sources';

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div>
          <Title1>Fabric Ops Studio</Title1>
          <Text size={200}>Management, operations and PowerShell</Text>
        </div>
        <div className={styles.sourceRow}>
          <Badge appearance="outline">INSPECT</Badge>
          <Badge appearance="filled">Provenance enabled</Badge>
        </div>
      </header>

      <div className={styles.body}>
        <nav className={styles.nav}>
          {nav.map(([label, Icon]) => (
            <Button key={label} className={styles.navButton} appearance={section === label ? 'primary' : 'subtle'} icon={<Icon />} onClick={() => setSection(label)}>
              {label}
            </Button>
          ))}
        </nav>

        <main className={styles.main}>
          {showLibrary ? (
            <>
              <div className={styles.hero}>
                <div>
                  <Title1>{section}</Title1>
                  <Text block>Every operation declares its upstream source, provider and risk level.</Text>
                </div>
                <Input className={styles.search} placeholder="Search command, category or provider" value={query} onChange={(_, data) => setQuery(data.value)} />
              </div>
              <Divider />
              <div className={styles.cards}>
                {filtered.map((cap) => (
                  <Card key={cap.id}>
                    <CardHeader header={<Subtitle1>{cap.title}</Subtitle1>} description={<Text>{cap.description}</Text>} />
                    <div className={styles.sourceRow}>
                      <Badge appearance="outline">{cap.category}</Badge>
                      <Badge appearance="outline">{cap.provider}</Badge>
                      <Badge appearance={cap.risk === 'read' ? 'tint' : 'filled'}>{cap.risk.toUpperCase()}</Badge>
                    </div>
                    <Text block size={200}>Source: {cap.source}</Text>
                    {cap.command && <Text block font="monospace">{cap.command}</Text>}
                    {cap.endpoint && <Text block size={200}>{cap.endpoint}</Text>}
                    <div className={styles.sourceRow}>
                      <Button size="small">Details</Button>
                      {cap.command && <Button size="small" appearance="secondary">Copy PowerShell</Button>}
                    </div>
                  </Card>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className={styles.hero}>
                <div>
                  <Title1>{section}</Title1>
                  <Text block>Operational control plane for Microsoft Fabric.</Text>
                </div>
              </div>
              {section === 'Overview' && (
                <>
                  <div className={styles.stats}>
                    {[['Workspaces', '—'], ['Capacities', '—'], ['Failed jobs', '—'], ['Git out-of-sync', '—']].map(([label, value]) => (
                      <Card key={label} className={styles.stat}>
                        <Subtitle1>{value}</Subtitle1>
                        <Text>{label}</Text>
                      </Card>
                    ))}
                  </div>
                  <div className={styles.cards}>
                    <Card><CardHeader header={<Subtitle1>Inventory tenant</Subtitle1>} description="List reachable workspaces and Fabric items." /><Button>Preview operation</Button></Card>
                    <Card><CardHeader header={<Subtitle1>Check failed jobs</Subtitle1>} description="Review recent failed item job instances." /><Button>Preview operation</Button></Card>
                    <Card><CardHeader header={<Subtitle1>Audit workspace security</Subtitle1>} description="Launch the upstream Fabric Security Audit tool." /><Button>Preview operation</Button></Card>
                    <Card><CardHeader header={<Subtitle1>PowerShell Library</Subtitle1>} description="Browse commands by Fabric resource and source." /><Button onClick={() => setSection('PowerShell Library')}>Open library</Button></Card>
                  </div>
                </>
              )}
              {section !== 'Overview' && <Card><CardHeader header={<Subtitle1>{section} module</Subtitle1>} description="The shell is ready; this module will be wired to capability providers without duplicating upstream implementation." /></Card>}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
