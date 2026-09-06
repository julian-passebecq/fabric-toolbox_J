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
import { useEffect, useMemo, useState } from 'react';
import { SpecializedTool, getSpecializedTools } from '../api/client';

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', marginBottom: '18px' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '14px' },
  badges: { display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '8px 0 12px' },
  code: { display: 'block', padding: '9px 10px', marginTop: '8px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  list: { margin: '8px 0 0', paddingLeft: '20px' },
  error: { color: tokens.colorPaletteRedForeground1 },
  muted: { color: tokens.colorNeutralForeground3 },
});

type SpecializedToolsPageProps = {
  category: string;
  title?: string;
  description?: string;
};

export function SpecializedToolsPage({ category, title, description }: SpecializedToolsPageProps) {
  const styles = useStyles();
  const [tools, setTools] = useState<SpecializedTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      setTools(await getSpecializedTools());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);
  const filtered = useMemo(() => tools.filter((tool) => tool.category === category), [tools, category]);

  async function copy(text: string) {
    await navigator.clipboard.writeText(text);
  }

  return (
    <>
      <div className={styles.header}>
        <div>
          <Title1>{title ?? category}</Title1>
          <Text block>{description ?? 'Specialized Microsoft Fabric Toolbox workflow with explicit prerequisites and execution boundaries.'}</Text>
        </div>
        <Button onClick={load}>Refresh</Button>
      </div>
      {loading && <Spinner label={`Loading ${category.toLowerCase()} tools`} />}
      {error && <Text block className={styles.error}>{error}</Text>}
      <div className={styles.grid}>
        {filtered.map((tool) => (
          <Card key={tool.id}>
            <CardHeader header={<Subtitle1>{tool.name}</Subtitle1>} description={<Text>{tool.description}</Text>} />
            <div className={styles.badges}>
              <Badge appearance={tool.available ? 'tint' : 'outline'}>{tool.available ? 'UPSTREAM PRESENT' : 'UPSTREAM MISSING'}</Badge>
              <Badge appearance="outline">{tool.execution_kind}</Badge>
              <Badge appearance="outline">{tool.status}</Badge>
              <Badge appearance="outline">{tool.risk.toUpperCase()}</Badge>
            </div>
            <Text block weight="semibold">Upstream</Text>
            <code className={styles.code}>{tool.upstream_path}</code>
            <Text block weight="semibold">Entrypoint</Text>
            <code className={styles.code}>{tool.entrypoint}</code>
            <Text block weight="semibold">Prerequisites</Text>
            <ul className={styles.list}>
              {tool.prerequisites.map((item) => <li key={item}><Text>{item}</Text></li>)}
            </ul>
            <Text block weight="semibold">Reference command / workflow</Text>
            <code className={styles.code}>{tool.example}</code>
            <Button size="small" onClick={() => copy(tool.example)}>Copy reference</Button>
            <Text block className={styles.muted}>{tool.reason}</Text>
          </Card>
        ))}
      </div>
      {!loading && filtered.length === 0 && <Text>No registered specialized tool for this category.</Text>}
    </>
  );
}
