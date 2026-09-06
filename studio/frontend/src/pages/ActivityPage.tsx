import {
  Badge,
  Button,
  Card,
  CardHeader,
  Spinner,
  Text,
  Title1,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useEffect, useState } from 'react';
import { ActivityRecord, getActivity } from '../api/client';

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', marginBottom: '18px' },
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

export function ActivityPage() {
  const styles = useStyles();
  const [records, setRecords] = useState<ActivityRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      setRecords(await getActivity());
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
          <Title1>Activity Log</Title1>
          <Text block>Local execution history with provider/source context and sensitive-field redaction.</Text>
        </div>
        <Button onClick={load}>Refresh</Button>
      </div>
      {loading && <Spinner label="Loading activity" />}
      {error && <Text block className={styles.error}>{error}</Text>}
      {!loading && records.length === 0 && <Text className={styles.muted}>No Studio operations have been executed yet.</Text>}
      <div className={styles.list}>
        {records.map((record, index) => (
          <Card key={`${text(record.timestamp)}-${index}`}>
            <CardHeader
              header={<Text weight="semibold">{text(record.action) || 'operation'}</Text>}
              description={<Text>{text(record.timestamp)}</Text>}
            />
            <div className={styles.badges}>
              {record.provider && <Badge appearance="outline">{text(record.provider)}</Badge>}
              {record.risk && <Badge appearance="outline">{text(record.risk).toUpperCase()}</Badge>}
              {record.capability_id && <Badge appearance="tint">{text(record.capability_id)}</Badge>}
            </div>
            {record.source_path && <Text block>Source: {text(record.source_path)}</Text>}
            {record.rendered_command && <code className={styles.code}>{text(record.rendered_command)}</code>}
          </Card>
        ))}
      </div>
    </>
  );
}
