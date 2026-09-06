import {
  Button,
  Input,
  Text,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useMemo, useState } from 'react';

const useStyles = makeStyles({
  root: { marginTop: '12px' },
  actions: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '10px' },
  filter: { minWidth: '240px', flexGrow: 1, maxWidth: '420px' },
  tableWrap: { overflow: 'auto', maxHeight: '440px', border: `1px solid ${tokens.colorNeutralStroke2}`, borderRadius: tokens.borderRadiusMedium },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '12px' },
  th: { textAlign: 'left', position: 'sticky', top: 0, zIndex: 1, backgroundColor: tokens.colorNeutralBackground3, padding: '8px', borderBottom: `1px solid ${tokens.colorNeutralStroke1}`, cursor: 'pointer', userSelect: 'none' },
  td: { padding: '8px', verticalAlign: 'top', borderBottom: `1px solid ${tokens.colorNeutralStroke3}`, maxWidth: '360px', overflowWrap: 'anywhere' },
  raw: { maxHeight: '440px', overflow: 'auto', padding: '12px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', fontSize: '12px', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' },
  muted: { color: tokens.colorNeutralForeground3 },
});

type ResultViewerProps = {
  result: Record<string, unknown>;
  fileName?: string;
};

type SortState = { column: string; direction: 'asc' | 'desc' } | null;

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
  })).slice(0, 18);
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function comparable(value: unknown): string | number {
  if (typeof value === 'number') return value;
  if (typeof value === 'boolean') return value ? 1 : 0;
  return displayValue(value).toLocaleLowerCase();
}

function csvCell(value: unknown): string {
  const text = value === null || value === undefined ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function downloadBlob(content: string, type: string, fileName: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function ResultViewer({ result, fileName = 'fabric-result.json' }: ResultViewerProps) {
  const styles = useStyles();
  const [showRaw, setShowRaw] = useState(false);
  const [filter, setFilter] = useState('');
  const [sort, setSort] = useState<SortState>(null);
  const rows = useMemo(() => extractRows(result), [result]);
  const columns = useMemo(() => primitiveColumns(rows), [rows]);
  const json = useMemo(() => JSON.stringify(result, null, 2), [result]);

  const visibleRows = useMemo(() => {
    const q = filter.trim().toLocaleLowerCase();
    const filtered = q
      ? rows.filter((row) => columns.some((column) => displayValue(row[column]).toLocaleLowerCase().includes(q)))
      : [...rows];
    if (!sort) return filtered;
    return filtered.sort((left, right) => {
      const a = comparable(left[sort.column]);
      const b = comparable(right[sort.column]);
      const direction = sort.direction === 'asc' ? 1 : -1;
      if (typeof a === 'number' && typeof b === 'number') return (a - b) * direction;
      return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' }) * direction;
    });
  }, [rows, columns, filter, sort]);

  function changeSort(column: string) {
    setSort((current) => {
      if (!current || current.column !== column) return { column, direction: 'asc' };
      if (current.direction === 'asc') return { column, direction: 'desc' };
      return null;
    });
  }

  async function copyJson() {
    await navigator.clipboard.writeText(json);
  }

  function downloadJson() {
    downloadBlob(json, 'application/json;charset=utf-8', fileName);
  }

  function downloadCsv() {
    const header = columns.map(csvCell).join(',');
    const body = visibleRows.map((row) => columns.map((column) => csvCell(row[column])).join(',')).join('\r\n');
    const csvName = fileName.replace(/\.json$/i, '') + '.csv';
    downloadBlob(`\uFEFF${header}\r\n${body}`, 'text/csv;charset=utf-8', csvName);
  }

  return (
    <div className={styles.root}>
      <div className={styles.actions}>
        <Text weight="semibold">Result</Text>
        {rows.length > 0 && <Text className={styles.muted}>{visibleRows.length}/{rows.length} rows</Text>}
        {!showRaw && rows.length > 1 && (
          <Input className={styles.filter} placeholder="Filter visible rows" value={filter} onChange={(_, data) => setFilter(data.value)} />
        )}
        <Button size="small" onClick={() => setShowRaw((current) => !current)}>{showRaw ? 'Show table' : 'Show raw JSON'}</Button>
        <Button size="small" onClick={copyJson}>Copy JSON</Button>
        <Button size="small" onClick={downloadJson}>Download JSON</Button>
        {!showRaw && rows.length > 0 && columns.length > 0 && <Button size="small" onClick={downloadCsv}>Download CSV</Button>}
      </div>

      {!showRaw && rows.length > 0 && columns.length > 0 ? (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column} className={styles.th} onClick={() => changeSort(column)} title="Click to sort; click again to reverse; third click clears sort">
                    {column}{sort?.column === column ? (sort.direction === 'asc' ? ' ▲' : ' ▼') : ''}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row, index) => (
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
