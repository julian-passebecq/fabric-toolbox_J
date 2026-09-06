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
import { SourceRegistry, getSources } from '../api/client';

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', marginBottom: '18px' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '14px', marginTop: '18px' },
  badges: { display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '8px 0' },
  code: { display: 'block', padding: '9px 10px', marginTop: '6px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  error: { color: tokens.colorPaletteRedForeground1 },
  muted: { color: tokens.colorNeutralForeground3 },
  excluded: { marginTop: '24px' },
  label: { marginTop: '8px' },
});

export function SourcesPage() {
  const styles = useStyles();
  const [registry, setRegistry] = useState<SourceRegistry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      setRegistry(await getSources());
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
          <Title1>Sources</Title1>
          <Text block>Feature provenance, execution transport and update strategy for every upstream dependency used by Fabric Ops Studio.</Text>
        </div>
        <Button onClick={load}>Refresh</Button>
      </div>
      {loading && <Spinner label="Loading source registry" />}
      {error && <Text block className={styles.error}>{error}</Text>}
      {registry && (
        <>
          <div className={styles.grid}>
            {registry.sources.map((source) => (
              <Card key={source.id}>
                <CardHeader header={<Subtitle1>{source.name}</Subtitle1>} description={<Text>{source.origin}</Text>} />
                <div className={styles.badges}>
                  {source.role && <Badge appearance="outline">{source.role}</Badge>}
                  {source.integration && <Badge appearance="outline">{source.integration}</Badge>}
                  {source.feature_source === false && <Badge appearance="tint">TRANSPORT ONLY</Badge>}
                </div>
                {source.repository && <Text block>Repository: {source.repository}</Text>}
                {source.local_path && <><Text block weight="semibold" className={styles.label}>Upstream path</Text><code className={styles.code}>{source.local_path}</code></>}
                {source.execution_transport && <><Text block weight="semibold" className={styles.label}>Execution transport</Text><code className={styles.code}>{source.execution_transport}</code></>}
                {source.authentication_transport && <><Text block weight="semibold" className={styles.label}>Authentication transport</Text><code className={styles.code}>{source.authentication_transport}</code></>}
                {source.update_strategy && <Text block className={styles.label}>Update strategy: {source.update_strategy}</Text>}
                {source.note && <Text block className={styles.muted}>{source.note}</Text>}
              </Card>
            ))}
          </div>
          <section className={styles.excluded}>
            <Subtitle1>Explicitly outside the product surface</Subtitle1>
            <div className={styles.grid}>
              {(registry.excluded_from_product_surface ?? []).map((item) => (
                <Card key={item.id}>
                  <CardHeader header={<Text weight="semibold">{item.id}</Text>} description={<Text>{item.reason}</Text>} />
                </Card>
              ))}
            </div>
          </section>
        </>
      )}
    </>
  );
}
