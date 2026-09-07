import {
  Badge,
  Button,
  Card,
  CardHeader,
  Subtitle1,
  Text,
  Title1,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useEffect, useMemo, useState } from 'react';
import { Capability } from '../api/client';
import { CommandWorkbench } from '../components/CommandWorkbench';

const FAVORITES_KEY = 'fabric-ops-studio.favorite-capabilities.v1';
const SELECTION_KEY_PREFIX = 'fabric-ops-studio.selected-operation.v1:';

const useStyles = makeStyles({
  header: { marginBottom: '18px' },
  toolbar: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', margin: '10px 0 16px' },
  context: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', padding: '10px 12px', marginBottom: '16px', border: `1px solid ${tokens.colorNeutralStroke2}`, borderRadius: tokens.borderRadiusMedium, backgroundColor: tokens.colorNeutralBackground2 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '12px' },
  badges: { display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '8px 0' },
  actions: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' },
  code: { display: 'block', padding: '8px 10px', margin: '8px 0', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  muted: { color: tokens.colorNeutralForeground3 },
});

type OperationsPageProps = {
  title: string;
  description: string;
  capabilities: Capability[];
  connected: boolean;
  defaultParameters?: Record<string, string | boolean>;
};

function readFavorites(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(FAVORITES_KEY) ?? '[]');
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
  } catch {
    return [];
  }
}

function selectionKey(title: string) {
  return `${SELECTION_KEY_PREFIX}${title.toLowerCase().replace(/\s+/g, '-')}`;
}

function compactValue(value: string | boolean): string {
  const text = String(value);
  if (text.length <= 22) return text;
  return `${text.slice(0, 8)}…${text.slice(-8)}`;
}

export function OperationsPage({ title, description, capabilities, connected, defaultParameters = {} }: OperationsPageProps) {
  const styles = useStyles();
  const [selected, setSelected] = useState<Capability | null>(null);
  const [favoriteIds, setFavoriteIds] = useState<string[]>(() => readFavorites());
  const [favoritesOnly, setFavoritesOnly] = useState(false);

  useEffect(() => {
    const remembered = localStorage.getItem(selectionKey(title));
    const preferred = capabilities.find((capability) => capability.id === remembered) ?? capabilities[0] ?? null;
    if (!selected || !capabilities.some((capability) => capability.id === selected.id)) {
      setSelected(preferred);
    }
  }, [capabilities, selected, title]);

  const visibleCapabilities = useMemo(
    () => favoritesOnly ? capabilities.filter((capability) => favoriteIds.includes(capability.id)) : capabilities,
    [capabilities, favoriteIds, favoritesOnly],
  );

  const inheritedContext = useMemo(() => {
    if (!selected) return [] as Array<[string, string | boolean]>;
    const accepted = new Set((selected.parameter_specs ?? []).map((parameter) => parameter.name));
    return Object.entries(defaultParameters).filter(([name, value]) => accepted.has(name) && value !== '' && value !== false);
  }, [defaultParameters, selected]);

  const missingRequired = useMemo(() => {
    if (!selected) return [];
    return (selected.parameter_specs ?? [])
      .filter((parameter) => parameter.mandatory)
      .filter((parameter) => {
        const value = defaultParameters[parameter.name];
        return value === undefined || value === '' || value === false;
      })
      .map((parameter) => parameter.name);
  }, [defaultParameters, selected]);

  function choose(capability: Capability) {
    setSelected(capability);
    localStorage.setItem(selectionKey(title), capability.id);
  }

  function toggleFavorite(capabilityId: string) {
    setFavoriteIds((current) => {
      const next = current.includes(capabilityId)
        ? current.filter((id) => id !== capabilityId)
        : [...current, capabilityId];
      localStorage.setItem(FAVORITES_KEY, JSON.stringify(next));
      return next;
    });
  }

  return (
    <>
      <div className={styles.header}>
        <Title1>{title}</Title1>
        <Text block>{description}</Text>
      </div>

      <div className={styles.toolbar}>
        <Button size="small" appearance={favoritesOnly ? 'primary' : 'secondary'} onClick={() => setFavoritesOnly((value) => !value)}>
          {favoritesOnly ? 'Showing favorites' : 'Favorites only'}
        </Button>
        <Text className={styles.muted}>{favoriteIds.filter((id) => capabilities.some((capability) => capability.id === id)).length} favorite operation(s) on this page</Text>
      </div>

      {selected && (inheritedContext.length > 0 || missingRequired.length > 0) && (
        <div className={styles.context}>
          <Text weight="semibold">Selected operation context</Text>
          {inheritedContext.map(([name, value]) => (
            <Badge key={name} appearance="tint">{name}: {compactValue(value)}</Badge>
          ))}
          {missingRequired.map((name) => (
            <Badge key={name} appearance="outline">Enter {name}</Badge>
          ))}
        </div>
      )}

      <div className={styles.grid}>
        {visibleCapabilities.map((capability) => {
          const favorite = favoriteIds.includes(capability.id);
          return (
            <Card key={capability.id}>
              <CardHeader header={<Subtitle1>{capability.title}</Subtitle1>} description={<Text>{capability.description}</Text>} />
              <div className={styles.badges}>
                <Badge appearance="outline">{capability.provider}</Badge>
                <Badge appearance={capability.risk === 'read' ? 'tint' : 'outline'}>{capability.risk.toUpperCase()}</Badge>
                {capability.execution_policy && <Badge appearance="outline">{capability.execution_policy.toUpperCase()}</Badge>}
                {capability.supports_whatif && <Badge appearance="tint">WHATIF</Badge>}
                {capability.response_mode === 'fabric-lro' && <Badge appearance="tint">FABRIC LRO</Badge>}
                {capability.generated && <Badge appearance="ghost">AUTO-DISCOVERED</Badge>}
                {favorite && <Badge appearance="tint">FAVORITE</Badge>}
              </div>
              {capability.command && <code className={styles.code}>{capability.command}</code>}
              {capability.endpoint && <code className={styles.code}>{capability.endpoint}</code>}
              {capability.source_path && <Text block size={200} className={styles.muted}>{capability.source_path}</Text>}
              <div className={styles.actions}>
                <Button appearance={selected?.id === capability.id ? 'primary' : 'secondary'} onClick={() => choose(capability)}>
                  {selected?.id === capability.id ? 'Selected' : capability.execution_policy === 'guarded-write' ? 'Plan change' : 'Open'}
                </Button>
                <Button appearance="subtle" onClick={() => toggleFavorite(capability.id)}>{favorite ? '★ Saved' : '☆ Save'}</Button>
              </div>
            </Card>
          );
        })}
      </div>

      {selected && <CommandWorkbench capability={selected} connected={connected} defaultParameters={defaultParameters} />}
      {capabilities.length === 0 && <Text>No registered capability is available for this page.</Text>}
      {capabilities.length > 0 && visibleCapabilities.length === 0 && <Text className={styles.muted}>No favorites are saved for this page.</Text>}
    </>
  );
}
