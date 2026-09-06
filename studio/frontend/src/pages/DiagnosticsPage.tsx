import {
  Badge,
  Button,
  Card,
  CardHeader,
  Spinner,
  Subtitle1,
  Text,
  Title1,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useEffect, useState } from 'react';
import { Diagnostics, getDiagnostics } from '../api/client';

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', marginBottom: '18px' },
  summary: { display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '18px' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '12px' },
  code: { display: 'block', padding: '8px 10px', marginTop: '8px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  error: { color: tokens.colorPaletteRedForeground1 },
  muted: { color: tokens.colorNeutralForeground3 },
  section: { marginTop: '28px', paddingTop: '20px', borderTop: `1px solid ${tokens.colorNeutralStroke2}` },
});

export function DiagnosticsPage() {
  const styles = useStyles();
  const [data, setData] = useState<Diagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      setData(await getDiagnostics());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  return (
    <>
      <div className={styles.header}>
        <div>
          <Title1>Diagnostics</Title1>
          <Text block>Local runtime readiness for Studio, upstream Fabric tooling, guarded writes, source compatibility and specialized workflows.</Text>
        </div>
        <Button onClick={load}>Refresh</Button>
      </div>
      {loading && <Spinner label="Checking runtime" />}
      {error && <Text block className={styles.error}>{error}</Text>}
      {data && (
        <>
          <div className={styles.summary}>
            <Badge appearance={data.status === 'ready' ? 'tint' : 'outline'}>{data.status.toUpperCase()}</Badge>
            <Badge appearance="outline">Python {data.python}</Badge>
            <Badge appearance="outline">Catalog {data.catalog.total}</Badge>
            <Badge appearance="tint">Guarded {data.catalog.policies['guarded-write'] ?? 0}</Badge>
            <Badge appearance="outline">Blocked {data.catalog.policies.blocked ?? 0}</Badge>
            <Badge appearance={data.compatibility.status === 'compatible' ? 'tint' : 'filled'}>{data.compatibility.status.toUpperCase()}</Badge>
            <Badge appearance={data.session.connected ? 'tint' : 'outline'}>{data.session.connected ? 'FABRIC CONNECTED' : 'FABRIC OFFLINE'}</Badge>
          </div>
          <Text block className={styles.muted}>{data.platform}</Text>
          <div className={styles.grid}>
            {data.checks.map((check) => (
              <Card key={check.name}>
                <CardHeader
                  header={<Subtitle1>{check.name}</Subtitle1>}
                  action={<Badge appearance={check.ok ? 'tint' : 'outline'}>{check.ok ? 'OK' : check.required ? 'REQUIRED' : 'OPTIONAL'}</Badge>}
                />
                <code className={styles.code}>{check.detail}</code>
              </Card>
            ))}
          </div>

          <section className={styles.section}>
            <Subtitle1>Capability compatibility</Subtitle1>
            <Text block className={styles.muted}>Static audit of the combined catalog after upstream merges: duplicate IDs, broken verification references, guarded-write policy inconsistencies, REST endpoint shape and repository-local source paths.</Text>
            <div className={styles.summary}>
              <Badge appearance={data.compatibility.errors === 0 ? 'tint' : 'filled'}>{data.compatibility.errors} errors</Badge>
              <Badge appearance={data.compatibility.warnings === 0 ? 'tint' : 'outline'}>{data.compatibility.warnings} warnings</Badge>
              <Badge appearance="outline">{data.compatibility.local_sources_checked} source paths checked</Badge>
              <Badge appearance="outline">{data.compatibility.local_sources_missing} missing</Badge>
            </div>
            <div className={styles.grid}>
              {data.compatibility.issues.map((issue, index) => (
                <Card key={`${issue.capability_id}-${index}`}>
                  <CardHeader
                    header={<Subtitle1>{issue.capability_id}</Subtitle1>}
                    action={<Badge appearance={issue.severity === 'error' ? 'filled' : 'outline'}>{issue.severity.toUpperCase()}</Badge>}
                  />
                  <Text>{issue.message}</Text>
                </Card>
              ))}
            </div>
            {data.compatibility.issues.length === 0 && <Text block>No catalog compatibility issues detected.</Text>}
          </section>
        </>
      )}
    </>
  );
}
