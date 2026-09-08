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
import { useRequestScope } from '../api/scope';
import { Capability, executeCapability, getSession } from '../api/client';

const RECENT_SELECTIONS_KEY = 'fabric-ops-studio.recent-inventory-selections.v2';
const LEGACY_RECENT_SELECTIONS_KEY = 'fabric-ops-studio.recent-inventory-selections.v1';

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
type RecentSelection = {
  tenantId: string;
  scope: string;
  id: string;
  name: string;
  type?: string;
  usedAt: string;
};

type InventoryPageProps = {
  title: string;
  description: string;
  connected: boolean;
  capability?: Capability;
  parameters?: Record<string, unknown>;
  fields?: InventoryField[];
  selectedRowId?: string;
  selectLabel?: string;
  recentScope?: string;
  recentLabel?: string;
  onSelectRow?: (row: Record<string, unknown>) => void;
};

function normaliseRows(result: Record<string, unknown>): Record<string, unknown>[] {
  const payload = result.studio_envelope === 1 ? result.data : result.output ?? result;
  if (Array.isArray(payload)) return payload.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null);
  if (payload && typeof payload === 'object') {
    const object = payload as Record<string, unknown>;
    for (const key of ['value', 'items', 'data', 'results']) {
      if (Array.isArray(object[key])) {
        return object[key].filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null);
      }
    }
    return [object];
  }
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

function parseRecentSelections(raw: string | null, legacy = false): RecentSelection[] {
  try {
    const parsed = JSON.parse(raw ?? '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed.flatMap((item): RecentSelection[] => {
      if (!item || typeof item !== 'object') return [];
      const value = item as Record<string, unknown>;
      if (typeof value.tenantId !== 'string' || typeof value.id !== 'string' || typeof value.name !== 'string') return [];
      return [{
        tenantId: value.tenantId,
        scope: typeof value.scope === 'string' ? value.scope : legacy ? 'workspaces' : 'default',
        id: value.id,
        name: value.name,
        type: typeof value.type === 'string' ? value.type : undefined,
        usedAt: typeof value.usedAt === 'string' ? value.usedAt : '',
      }];
    });
  } catch {
    return [];
  }
}

function readRecentSelections(): RecentSelection[] {
  const current = parseRecentSelections(localStorage.getItem(RECENT_SELECTIONS_KEY));
  if (current.length > 0) return current;
  const legacy = parseRecentSelections(localStorage.getItem(LEGACY_RECENT_SELECTIONS_KEY), true);
  if (legacy.length > 0) localStorage.setItem(RECENT_SELECTIONS_KEY, JSON.stringify(legacy));
  return legacy;
}

export function InventoryPage({
  title,
  description,
  connected,
  capability,
  parameters = {},
  fields,
  selectedRowId,
  selectLabel = 'Use',
  recentScope = 'workspaces',
  recentLabel = 'Recent for this tenant',
  onSelectRow,
}: InventoryPageProps) {
  const styles = useStyles();
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [renderedCommand, setRenderedCommand] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [tenantId, setTenantId] = useState('');
  const [recentSelections, setRecentSelections] = useState<RecentSelection[]>(() => readRecentSelections());
  const parameterSignature = JSON.stringify(parameters);
  const scope = useRequestScope(`${capability?.id}:${parameterSignature}:${connected}`);
  const visibleFields = useMemo(() => fields && fields.length > 0 ? fields : discoverFields(rows), [fields, rows]);
  const tenantRecent = useMemo(
    () => tenantId ? recentSelections.filter((item) => item.tenantId === tenantId && item.scope === recentScope).slice(0, 6) : [],
    [recentScope, recentSelections, tenantId],
  );
  const missingRequired = useMemo(() => {
    if (!capability?.parameter_specs) return [];
    return capability.parameter_specs
      .filter((parameter) => parameter.mandatory)
      .filter((parameter) => parameters[parameter.name] === undefined || parameters[parameter.name] === null || parameters[parameter.name] === '')
      .map((parameter) => parameter.name);
  }, [capability, parameterSignature]);

  useEffect(() => {
    if (!onSelectRow || !connected) return;
    let cancelled = false;
    getSession().then((session) => {
      if (!cancelled) setTenantId(session.tenant_id ?? '');
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [connected, onSelectRow]);

  useEffect(() => {
    setRows([]);
    setRenderedCommand('');
    setError('');
    setLoading(false);
  }, [parameterSignature, capability?.id, connected]);

  async function load() {
    if (!capability || missingRequired.length > 0) return;
    const active = scope.start();
    setLoading(true);
    setError('');
    try {
      const response = await executeCapability(capability.id, parameters, active.signal);
      if (!active.current()) return;
      setRenderedCommand(response.rendered_command);
      setRows(normaliseRows(response.result));
    } catch (err) {
      if (!active.current()) return;
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      active.finish();
      if (active.current()) setLoading(false);
    }
  }

  function selectRow(row: Record<string, unknown>) {
    onSelectRow?.(row);
    if (!tenantId) return;
    const rawId = row.id ?? row.Id ?? row.workspaceId ?? row.WorkspaceId ?? row.itemId ?? row.ItemId;
    if (rawId === null || rawId === undefined) return;
    const id = String(rawId);
    const name = displayValue(row.displayName ?? row.DisplayName ?? row.name ?? row.Name ?? id);
    const type = row.type ?? row.Type ?? row.itemType ?? row.ItemType;
    setRecentSelections((current) => {
      const next = [
        { tenantId, scope: recentScope, id, name, type: type === null || type === undefined ? undefined : String(type), usedAt: new Date().toISOString() },
        ...current.filter((item) => !(item.tenantId === tenantId && item.scope === recentScope && item.id === id)),
      ].slice(0, 40);
      localStorage.setItem(RECENT_SELECTIONS_KEY, JSON.stringify(next));
      return next;
    });
  }

  function useRecent(selection: RecentSelection) {
    const liveRow = rows.find((row) => String(row.id ?? row.Id ?? row.workspaceId ?? row.WorkspaceId ?? row.itemId ?? row.ItemId ?? '') === selection.id);
    const row = liveRow ?? { id: selection.id, displayName: selection.name, type: selection.type };
    onSelectRow?.(row);
  }

  return (
    <>
      <div className={styles.header}>
        <div>
          <Title1>{title}</Title1>
          <Text block>{description}</Text>
        </div>
        <Button appearance="primary" disabled={!connected || !capability || loading || missingRequired.length > 0} onClick={load}>
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
          <code className={styles.code}>{capability.command ?? capability.endpoint}</code>
          {capability.source_path && <Text block className={styles.muted}>{capability.source_path}</Text>}
        </>
      )}

      {onSelectRow && tenantRecent.length > 0 && (
        <div className={styles.recent}>
          <Text weight="semibold">{recentLabel}</Text>
          {tenantRecent.map((selection) => (
            <Button key={selection.id} size="small" appearance={selectedRowId === selection.id ? 'primary' : 'secondary'} onClick={() => useRecent(selection)}>
              {selection.name}
            </Button>
          ))}
        </div>
      )}

      {!connected && <Text block className={styles.muted}>Connect to a Fabric tenant using the bar above before running inventory.</Text>}
      {connected && missingRequired.length > 0 && <Text block className={styles.muted}>Select the required context first: {missingRequired.join(', ')}.</Text>}
      {loading && <Spinner label={`Loading ${title.toLowerCase()}`} />}
      {error && <Text role="alert" block className={styles.error}>{error}</Text>}
      {renderedCommand && <Text block className={styles.muted}>Executed: {renderedCommand}</Text>}
      {!loading && rows.length === 0 && connected && missingRequired.length === 0 && <Text block className={styles.muted}>No results loaded yet. Use Refresh to query the upstream provider.</Text>}

      <div className={styles.grid}>
        {rows.map((row, index) => {
          const rawId = row.id ?? row.Id ?? row.itemId ?? row.ItemId;
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
