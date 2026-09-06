import {
  Button,
  Text,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useMemo, useState } from 'react';

const useStyles = makeStyles({
  root: { marginTop: '12px' },
  actions: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '10px' },
  tableWrap: { overflow: 'auto', maxHeight: '440px', border: `1px solid ${tokens.colorNeutralStroke2}`, borderRadius: tokens.borderRadiusMedium },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '12px' },
  th: { textAlign: 'left', position: 'sticky', top: 0, zIndex: 1, backgroundColor: tokens.colorNeutralBackground3, padding: '8px', borderBottom: `1px solid ${tokens.colorNeutralStroke1}` },
  td: { padding: '8px', verticalAlign: 'top', borderBottom: `1px solid ${tokens.colorNeutralStroke3}`, maxWidth: '360px', overflowWrap: 'anywhere' },
  raw: { maxHeight: '440px', overflow: 'auto', padding: '12px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', fontSize: '12px', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' },
  muted: { color: tokens.colorNeutralForeground3 },
});

type ResultViewerProps = {
  result: Record<string, unknown>;
  fileName?: string;
};

function objectRows(value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) {
    return value.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null && !Array.isArray(item));
  }
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return [value as Record<string, unknown>];
  }
  return [];
}

function extractRows(result: Record<string, unknown>): Record<string, unknown>[] {
  const direct = result.output ?? result;
  if (Array.isArray(direct)) return objectRows(direct);
  if (typeof direct !== 'object' || direct === null) return [];

  const object = direct as Record<string, unknown>;
  for (const key of ['value', 'items', 'data', 'results']) {
    if (Array.isArray(object[key])) return objectRows(object[key]);
  }
  return objectRows(object);
}

function primitiveColumns(rows: Record<string, unknown>[]): string[] {
  const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  return keys.filter((key) => rows.some((row) => {
    const value = row[key];
    return value === null || value === undefined || ['string', 'number', 'boolean'].includes(typeof value);
  })).slice(0, 14);
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function ResultViewer({ result, fileName = 'fabric-result.json' }: ResultViewerProps) {
  const styles = useStyles();
  const [showRaw, setShowRaw] = useState(false);
  const rows = useMemo(() => extractRows(result), [result]);
  const columns = useMemo(() => primitiveColumns(rows), [rows]);
  const json = useMemo(() => JSON.stringify(result, null, 2), [result]);

  async function copyJson() {
    await navigator.clipboard.writeText(json);
  }

  function downloadJson() {
    const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className={styles.root}>
      <div className={styles.actions}>
        <Text weight="semibold">Result</Text>
        {rows.length > 0 && <Text className={styles.muted}>{rows.length} row{rows.length === 1 ? '' : 's'}</Text>}
        <Button size="small" onClick={() => setShowRaw((current) => !current)}>{showRaw ? 'Show table' : 'Show raw JSON'}</Button>
        <Button size="small" onClick={copyJson}>Copy JSON</Button>
        <Button size="small" onClick={downloadJson}>Download JSON</Button>
      </div>

      {!showRaw && rows.length > 0 && columns.length > 0 ? (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>{columns.map((column) => <th key={column} className={styles.th}>{column}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={String(row.id ?? row.Id ?? index)}>
                  {columns.map((column) => <td key={column} className={styles.td}>{displayValue(row[column])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <pre className={styles.raw}>{json}</pre>
      )}
    </div>
  );
}
