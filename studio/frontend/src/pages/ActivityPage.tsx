import {
  Badge,
  Button,
  Card,
  CardHeader,
  Input,
  Spinner,
  Text,
  Title1,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useEffect, useMemo, useState } from 'react';
import { ActivityRecord, getActivity } from '../api/client';

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', marginBottom: '18px' },
  toolbar: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '14px' },
  search: { minWidth: '280px', maxWidth: '480px', flexGrow: 1 },
  list: { display: 'grid', gap: '10px' },
  badges: { display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px' },
  code: { display: 'block', padding: '9px 10px', marginTop: '8px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  error: { color: tokens.colorPaletteRedForeground1 },
  muted: { color: tokens.colorNeutralForeground3 },
});

function text(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function download(content: string, fileName: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function ActivityPage() {
  const styles = useStyles();
  const [records, setRecords] = useState<ActivityRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      setRecords(await getActivity(500));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return records;
    return records.filter((record) => JSON.stringify(record).toLowerCase().includes(q));
  }, [records, query]);

  function exportJson() {
    download(JSON.stringify(filtered, null, 2), 'fabric-ops-activity.json', 'application/json;charset=utf-8');
  }

  function exportJsonl() {
    const jsonl = filtered.map((record) => JSON.stringify(record)).join('\n');
    download(jsonl, 'fabric-ops-activity.jsonl', 'application/x-ndjson;charset=utf-8');
  }

  return (
    <>
      <div className={styles.header}>
        <div>
          <Title1>Activity Log</Title1>
          <Text block>Local execution history with provider/source context and sensitive-field redaction.</Text>
        </div>
        <Button onClick={load}>Refresh</Button>
      </div>
      <div className={styles.toolbar}>
        <Input className={styles.search} placeholder="Filter action, provider, capability, command or result" value={query} onChange={(_, data) => setQuery(data.value)} />
        <Text className={styles.muted}>{filtered.length}/{records.length} events</Text>
        <Button size="small" onClick={exportJson} disabled={filtered.length === 0}>Export JSON</Button>
        <Button size="small" onClick={exportJsonl} disabled={filtered.length === 0}>Export JSONL</Button>
      </div>
      {loading && <Spinner label="Loading activity" />}
      {error && <Text block className={styles.error}>{error}</Text>}
      {!loading && records.length === 0 && <Text className={styles.muted}>No Studio operations have been executed yet.</Text>}
      {!loading && records.length > 0 && filtered.length === 0 && <Text className={styles.muted}>No activity matches the current filter.</Text>}
      <div className={styles.list}>
        {filtered.map((record, index) => (
          <Card key={`${text(record.timestamp)}-${index}`}>
            <CardHeader
              header={<Text weight="semibold">{text(record.action) || 'operation'}</Text>}
              description={<Text>{text(record.timestamp)}</Text>}
            />
            <div className={styles.badges}>
              {Boolean(record.provider) && <Badge appearance="outline">{text(record.provider)}</Badge>}
              {Boolean(record.risk) && <Badge appearance="outline">{text(record.risk).toUpperCase()}</Badge>}
              {Boolean(record.capability_id) && <Badge appearance="tint">{text(record.capability_id)}</Badge>}
              {Boolean(record.status) && <Badge appearance="outline">{text(record.status).toUpperCase()}</Badge>}
            </div>
            {Boolean(record.source_path) && <Text block>Source: {text(record.source_path)}</Text>}
            {Boolean(record.rendered_command) && <code className={styles.code}>{text(record.rendered_command)}</code>}
          </Card>
        ))}
      </div>
    </>
  );
}
