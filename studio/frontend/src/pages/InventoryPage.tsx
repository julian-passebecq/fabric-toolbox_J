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
import { useState } from 'react';
import { Capability, executeCapability } from '../api/client';

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', marginBottom: '18px' },
  source: { display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '10px 0 18px' },
  code: { display: 'block', padding: '10px 12px', marginTop: '8px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px', marginTop: '16px' },
  fields: { display: 'grid', gridTemplateColumns: '110px 1fr', gap: '5px 12px', marginTop: '8px' },
  error: { color: tokens.colorPaletteRedForeground1 },
  muted: { color: tokens.colorNeutralForeground3 },
});

type InventoryPageProps = {
  title: string;
  description: string;
  connected: boolean;
  capability?: Capability;
  fields: Array<{ key: string; label: string }>;
};

function normaliseRows(result: Record<string, unknown>): Record<string, unknown>[] {
  const payload = result.output ?? result;
  if (Array.isArray(payload)) return payload.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null);
  if (payload && typeof payload === 'object') return [payload as Record<string, unknown>];
  return [];
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function InventoryPage({ title, description, connected, capability, fields }: InventoryPageProps) {
  const styles = useStyles();
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [renderedCommand, setRenderedCommand] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function load() {
    if (!capability) return;
    setLoading(true);
    setError('');
    try {
      const response = await executeCapability(capability.id);
      setRenderedCommand(response.rendered_command);
      setRows(normaliseRows(response.result));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className={styles.header}>
        <div>
          <Title1>{title}</Title1>
          <Text block>{description}</Text>
        </div>
        <Button appearance="primary" disabled={!connected || !capability || loading} onClick={load}>
          Refresh
        </Button>
      </div>

      {capability && (
        <>
          <div className={styles.source}>
            <Badge appearance="outline">Feature: {capability.provider}</Badge>
            <Badge appearance="outline">Source: {capability.source}</Badge>
            <Badge appearance="tint">READ ONLY</Badge>
          </div>
          <code className={styles.code}>{capability.command}</code>
          {capability.source_path && <Text block className={styles.muted}>{capability.source_path}</Text>}
        </>
      )}

      {!connected && <Text block className={styles.muted}>Connect to a Fabric tenant using the bar above before running inventory.</Text>}
      {loading && <Spinner label={`Loading ${title.toLowerCase()}`} />}
      {error && <Text block className={styles.error}>{error}</Text>}
      {renderedCommand && <Text block className={styles.muted}>Executed: {renderedCommand}</Text>}

      <div className={styles.grid}>
        {rows.map((row, index) => {
          const cardKey = displayValue(row.id ?? row.Id ?? `${index}`);
          const heading = displayValue(row.displayName ?? row.DisplayName ?? row.name ?? row.Name ?? `${title} ${index + 1}`);
          return (
            <Card key={cardKey}>
              <CardHeader header={<Subtitle1>{heading}</Subtitle1>} />
              <div className={styles.fields}>
                {fields.map((field) => (
                  <div key={field.key} style={{ display: 'contents' }}>
                    <Text weight="semibold">{field.label}</Text>
                    <Text>{displayValue(row[field.key])}</Text>
                  </div>
                ))}
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
}
