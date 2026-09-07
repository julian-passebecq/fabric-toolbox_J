import {
  Badge,
  Button,
  Card,
  CardHeader,
  Subtitle1,
  Text,
  Title2,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { Capability } from '../api/client';
import { InventoryPage } from './InventoryPage';
import { OperationsPage } from './OperationsPage';

const useStyles = makeStyles({
  contextCard: { marginBottom: '18px' },
  contextRow: { display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' },
  section: { marginTop: '34px', paddingTop: '26px', borderTop: `1px solid ${tokens.colorNeutralStroke2}` },
  muted: { color: tokens.colorNeutralForeground3 },
});

export type WorkspaceContext = { id: string; name: string };
export type ItemContext = { id: string; name: string; type?: string };

type ItemExplorerPageProps = {
  connected: boolean;
  workspaceContext: WorkspaceContext | null;
  itemContext: ItemContext | null;
  catalog: Capability[];
  onSelectItem: (item: ItemContext) => void;
  onClearItem: () => void;
  onOpenRuns: () => void;
};

function rowValue(row: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = row[key];
    if (value !== null && value !== undefined && value !== '') return String(value);
  }
  return '';
}

export function ItemExplorerPage({
  connected,
  workspaceContext,
  itemContext,
  catalog,
  onSelectItem,
  onClearItem,
  onOpenRuns,
}: ItemExplorerPageProps) {
  const styles = useStyles();
  const listCapability = catalog.find((item) => item.id === 'rest-items-list');
  const itemCapabilities = catalog.filter((item) => ['rest-item-get', 'rest-item-connections-list'].includes(item.id));
  const runCapabilities = catalog.filter((item) => ['rest-job-instances-list', 'rest-schedules-list'].includes(item.id));

  const workspaceParameters: Record<string, unknown> = workspaceContext
    ? { workspaceId: workspaceContext.id }
    : {};
  const itemParameters: Record<string, string | boolean> = {};
  if (workspaceContext) itemParameters.workspaceId = workspaceContext.id;
  if (itemContext) itemParameters.itemId = itemContext.id;

  function selectItem(row: Record<string, unknown>) {
    const id = rowValue(row, ['id', 'Id', 'itemId', 'ItemId']);
    if (!id) return;
    const name = rowValue(row, ['displayName', 'DisplayName', 'name', 'Name']) || id;
    const type = rowValue(row, ['type', 'Type', 'itemType', 'ItemType']) || undefined;
    onSelectItem({ id, name, type });
  }

  return (
    <>
      <Card className={styles.contextCard}>
        <CardHeader
          header={<Title2>Item context</Title2>}
          description={<Text>Select a Fabric workspace first, then choose an item once. Studio reuses both IDs across detail, connection, run and schedule reads.</Text>}
        />
        <div className={styles.contextRow}>
          <Badge appearance={workspaceContext ? 'tint' : 'outline'}>
            Workspace: {workspaceContext?.name ?? 'None selected'}
          </Badge>
          <Badge appearance={itemContext ? 'tint' : 'outline'}>
            Item: {itemContext?.name ?? 'None selected'}
          </Badge>
          {itemContext?.type && <Badge appearance="outline">{itemContext.type}</Badge>}
          {itemContext && <Button size="small" appearance="subtle" onClick={onClearItem}>Clear item</Button>}
          {itemContext && <Button size="small" appearance="secondary" onClick={onOpenRuns}>Open runs & schedules</Button>}
        </div>
      </Card>

      {!workspaceContext && (
        <Text block className={styles.muted}>Choose a workspace on the Workspaces page before loading item inventory.</Text>
      )}

      <InventoryPage
        title="Workspace items"
        description="Generic Fabric item inventory from the official Items REST API. The active workspace is injected automatically; no workspace GUID needs to be pasted."
        connected={connected}
        capability={listCapability}
        parameters={workspaceParameters}
        fields={[
          { key: 'id', label: 'ID' },
          { key: 'type', label: 'Type' },
          { key: 'description', label: 'Description' },
          { key: 'folderId', label: 'Folder ID' },
        ]}
        selectedRowId={itemContext?.id}
        selectLabel="Use item"
        recentScope={workspaceContext ? `items:${workspaceContext.id}` : 'items:none'}
        recentLabel={workspaceContext ? `Recent items in ${workspaceContext.name}` : 'Recent items'}
        onSelectRow={selectItem}
      />

      <div className={styles.section}>
        <OperationsPage
          title="Item inspection"
          description="Read item metadata and connection dependencies. WorkspaceId and itemId are inherited from the selected contexts."
          capabilities={itemCapabilities}
          connected={connected}
          defaultParameters={itemParameters}
        />
      </div>

      <div className={styles.section}>
        <OperationsPage
          title="Item runs & schedules"
          description="Inspect job instances and schedules for the selected item. Schedule listing still requires its Fabric job type, but workspace and item identifiers are already supplied."
          capabilities={runCapabilities}
          connected={connected}
          defaultParameters={itemParameters}
        />
      </div>
    </>
  );
}
