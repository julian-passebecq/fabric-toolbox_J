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
import { useMemo, useState } from 'react';
import { Capability, executeCapability } from '../api/client';

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', marginBottom: '18px' },
  source: { display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '10px 0 18px' },
  code: { display: 'block', padding: '10px 12px', marginTop: '8px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '12px', marginTop: '16px' },
  fields: { display: 'grid', gridTemplateColumns: '120px 1fr', gap: '5px 12px', marginTop: '8px' },
  error: { color: tokens.colorPaletteRedForeground1 },
  muted: { color: tokens.colorNeutralForeground3 },
});

type InventoryField = { key: string; label: string };

type InventoryPageProps = {
  title: string;
  description: string;
  connected: boolean;
  capability?: Capability;
  fields?: InventoryField[];
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

function titleCase(key: string): string {
  return key
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .replace(/^./, (value) => value.toUpperCase());
}

function discoverFields(rows: Record<string, unknown>[]): InventoryField[] {
  if (rows.length === 0) return [];
  const preferred = ['id', 'displayName', 'name', 'type', 'connectivityType', 'gatewayId', 'privacyLevel', 'state', 'region', 'sku'];
  const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  const primitive = keys.filter((key) => rows.some((row) => {
    const value = row[key];
    return value === null || value === undefined || ['string', 'number', 'boolean'].includes(typeof value);
  }));
  primitive.sort((a, b) => {
    const ai = preferred.indexOf(a);
    const bi = preferred.indexOf(b);
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });
  return primitive.filter((key) => !['displayName', 'DisplayName', 'name', 'Name'].includes(key)).slice(0, 7).map((key) => ({ key, label: titleCase(key) }));
}

export function InventoryPage({ title, description, connected, capability, fields }: InventoryPageProps) {
  const styles = useStyles();
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [renderedCommand, setRenderedCommand] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const visibleFields = useMemo(() => fields && fields.length > 0 ? fields : discoverFields(rows), [fields, rows]);

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
      {!loading && rows.length === 0 && connected && <Text block className={styles.muted}>No results loaded yet. Use Refresh to query the upstream provider.</Text>}

      <div className={styles.grid}>
        {rows.map((row, index) => {
          const cardKey = displayValue(row.id ?? row.Id ?? `${index}`);
          const heading = displayValue(row.displayName ?? row.DisplayName ?? row.name ?? row.Name ?? `${title} ${index + 1}`);
          return (
            <Card key={cardKey}>
              <CardHeader header={<Subtitle1>{heading}</Subtitle1>} />
              <div className={styles.fields}>
                {visibleFields.map((field) => (
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
