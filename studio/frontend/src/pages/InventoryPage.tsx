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
import { Capability, executeCapability, getSession } from '../api/client';

const RECENT_SELECTIONS_KEY = 'fabric-ops-studio.recent-inventory-selections.v1';

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', marginBottom: '18px' },
  source: { display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '10px 0 18px' },
  recent: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', margin: '12px 0' },
  code: { display: 'block', padding: '10px 12px', marginTop: '8px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '12px', marginTop: '16px' },
  fields: { display: 'grid', gridTemplateColumns: '120px 1fr', gap: '5px 12px', marginTop: '8px' },
  error: { color: tokens.colorPaletteRedForeground1 },
  muted: { color: tokens.colorNeutralForeground3 },
});

type InventoryField = { key: string; label: string };
type RecentSelection = { tenantId: string; id: string; name: string; usedAt: string };

type InventoryPageProps = {
  title: string;
  description: string;
  connected: boolean;
  capability?: Capability;
  fields?: InventoryField[];
  selectedRowId?: string;
  selectLabel?: string;
  onSelectRow?: (row: Record<string, unknown>) => void;
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

function readRecentSelections(): RecentSelection[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(RECENT_SELECTIONS_KEY) ?? '[]');
    return Array.isArray(parsed)
      ? parsed.filter((item): item is RecentSelection => Boolean(item && typeof item.tenantId === 'string' && typeof item.id === 'string' && typeof item.name === 'string'))
      : [];
  } catch {
    return [];
  }
}

export function InventoryPage({ title, description, connected, capability, fields, selectedRowId, selectLabel = 'Use', onSelectRow }: InventoryPageProps) {
  const styles = useStyles();
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [renderedCommand, setRenderedCommand] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [tenantId, setTenantId] = useState('');
  const [recentSelections, setRecentSelections] = useState<RecentSelection[]>(() => readRecentSelections());
  const visibleFields = useMemo(() => fields && fields.length > 0 ? fields : discoverFields(rows), [fields, rows]);
  const tenantRecent = useMemo(
    () => tenantId ? recentSelections.filter((item) => item.tenantId === tenantId).slice(0, 6) : [],
    [recentSelections, tenantId],
  );

  useEffect(() => {
    if (!onSelectRow || !connected) return;
    let cancelled = false;
    getSession().then((session) => {
      if (!cancelled) setTenantId(session.tenant_id ?? '');
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [connected, onSelectRow]);

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

  function selectRow(row: Record<string, unknown>) {
    onSelectRow?.(row);
    if (!tenantId) return;
    const rawId = row.id ?? row.Id ?? row.workspaceId ?? row.WorkspaceId;
    if (rawId === null || rawId === undefined) return;
    const id = String(rawId);
    const name = displayValue(row.displayName ?? row.DisplayName ?? row.name ?? row.Name ?? id);
    setRecentSelections((current) => {
      const next = [
        { tenantId, id, name, usedAt: new Date().toISOString() },
        ...current.filter((item) => !(item.tenantId === tenantId && item.id === id)),
      ].slice(0, 24);
      localStorage.setItem(RECENT_SELECTIONS_KEY, JSON.stringify(next));
      return next;
    });
  }

  function useRecent(selection: RecentSelection) {
    const liveRow = rows.find((row) => String(row.id ?? row.Id ?? row.workspaceId ?? row.WorkspaceId ?? '') === selection.id);
    const row = liveRow ?? { id: selection.id, displayName: selection.name };
    onSelectRow?.(row);
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

      {onSelectRow && tenantRecent.length > 0 && (
        <div className={styles.recent}>
          <Text weight="semibold">Recent for this tenant</Text>
          {tenantRecent.map((selection) => (
            <Button key={selection.id} size="small" appearance={selectedRowId === selection.id ? 'primary' : 'secondary'} onClick={() => useRecent(selection)}>
              {selection.name}
            </Button>
          ))}
        </div>
      )}

      {!connected && <Text block className={styles.muted}>Connect to a Fabric tenant using the bar above before running inventory.</Text>}
      {loading && <Spinner label={`Loading ${title.toLowerCase()}`} />}
      {error && <Text block className={styles.error}>{error}</Text>}
      {renderedCommand && <Text block className={styles.muted}>Executed: {renderedCommand}</Text>}
      {!loading && rows.length === 0 && connected && <Text block className={styles.muted}>No results loaded yet. Use Refresh to query the upstream provider.</Text>}

      <div className={styles.grid}>
        {rows.map((row, index) => {
          const rawId = row.id ?? row.Id;
          const rowId = rawId === null || rawId === undefined ? '' : String(rawId);
          const cardKey = rowId || `${index}`;
          const heading = displayValue(row.displayName ?? row.DisplayName ?? row.name ?? row.Name ?? `${title} ${index + 1}`);
          const isSelected = Boolean(rowId && selectedRowId && rowId === selectedRowId);
          return (
            <Card key={cardKey}>
              <CardHeader
                header={<Subtitle1>{heading}</Subtitle1>}
                action={onSelectRow && rowId ? (
                  <Button size="small" appearance={isSelected ? 'primary' : 'secondary'} onClick={() => selectRow(row)}>
                    {isSelected ? 'Selected' : selectLabel}
                  </Button>
                ) : undefined}
              />
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
