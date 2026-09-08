import {
  Badge,
  Button,
  Card,
  CardHeader,
  Input,
  Spinner,
  Subtitle1,
  Text,
  Title1,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useEffect, useMemo, useState } from 'react';
import { MutationOutcome } from '../components/MutationOutcome';
import { ActivityRecord, MutationPlan, getActivity, getMutationPlans } from '../api/client';

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', marginBottom: '18px' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '12px' },
  badges: { display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '8px 0' },
  code: { display: 'block', padding: '8px 10px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  muted: { color: tokens.colorNeutralForeground3 },
  error: { color: tokens.colorPaletteRedForeground1 },
  section: { marginTop: '30px', paddingTop: '22px', borderTop: `1px solid ${tokens.colorNeutralStroke2}` },
  toolbar: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', margin: '8px 0 14px' },
  search: { minWidth: '260px', maxWidth: '440px', flexGrow: 1 },
});

function statusAppearance(status: MutationPlan['status']) {
  if (status === 'executed' || status === 'validated') return 'tint';
  if (status === 'failed' || status === 'expired') return 'filled';
  return 'outline';
}

function text(record: ActivityRecord, key: string): string {
  const value = record[key];
  if (value === null || value === undefined) return '';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

function mutationHistory(records: ActivityRecord[]) {
  return records.filter((record) => String(record.action ?? '').startsWith('mutation.'));
}

export function ChangePlansPage() {
  const styles = useStyles();
  const [plans, setPlans] = useState<MutationPlan[]>([]);
  const [history, setHistory] = useState<ActivityRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [currentPlans, activity] = await Promise.all([getMutationPlans(), getActivity(500)]);
      setPlans(currentPlans);
      setHistory(mutationHistory(activity));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const filteredHistory = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return history;
    return history.filter((record) => JSON.stringify(record).toLowerCase().includes(q));
  }, [history, query]);

  return (
    <>
      <div className={styles.header}>
        <div>
          <Title1>Change Plans</Title1>
          <Text block>Current approval plans are tenant-bound, expire after ten minutes and remain in memory only. Durable history below is reconstructed from the redacted activity log, so approval tokens and executable plans are never restored after restart.</Text>
        </div>
        <Button onClick={() => void load()} disabled={loading}>Refresh</Button>
      </div>

      {loading && <Spinner label="Loading mutation plans and history" />}
      {error && <Text block className={styles.error}>{error}</Text>}
      {!loading && !error && plans.length === 0 && <Text className={styles.muted}>No active mutation plans exist in this backend session.</Text>}

      <div className={styles.grid}>
        {plans.map((plan) => (
          <Card key={plan.plan_id}>
            <CardHeader
              header={<Subtitle1>{plan.capability_title}</Subtitle1>}
              description={<Text>Plan {plan.plan_id.slice(0, 8).toUpperCase()}</Text>}
            />
            <div className={styles.badges}>
              <MutationOutcome status={plan.status} /><Badge appearance={statusAppearance(plan.status)}>{plan.status.toUpperCase()}</Badge>
              <Badge appearance="outline">{plan.risk.toUpperCase()}</Badge>
              <Badge appearance="outline">Tenant-bound</Badge>
              {plan.supports_validation && <Badge appearance="tint">WHATIF</Badge>}
            </div>
            <Text block size={200}>Tenant: {plan.tenant_id}</Text>
            <Text block size={200}>Created: {new Date(plan.created_at).toLocaleString()}</Text>
            <Text block size={200}>Expires: {new Date(plan.expires_at).toLocaleString()}</Text>
            <Text block size={200} className={styles.muted}>Digest: {plan.digest}</Text>
            <code className={styles.code}>{plan.rendered_command}</code>
          </Card>
        ))}
      </div>

      <section className={styles.section}>
        <Subtitle1>Durable mutation history</Subtitle1>
        <Text block className={styles.muted}>Derived from the existing redacted activity log. This survives backend restarts without persisting approval text or reusable execution state.</Text>
        <div className={styles.toolbar}>
          <Input className={styles.search} placeholder="Filter action, capability, plan, status or tenant" value={query} onChange={(_, data) => setQuery(data.value)} />
          <Text className={styles.muted}>{filteredHistory.length}/{history.length} events</Text>
        </div>
        <div className={styles.grid}>
          {filteredHistory.map((record, index) => {
            const action = text(record, 'action') || 'mutation.event';
            const planId = text(record, 'plan_id');
            const capability = text(record, 'capability_id');
            const status = text(record, 'status');
            const timestamp = text(record, 'timestamp');
            return (
              <Card key={`${timestamp}-${planId}-${index}`}>
                <CardHeader header={<Subtitle1>{action}</Subtitle1>} description={<Text>{timestamp ? new Date(timestamp).toLocaleString() : 'Timestamp unavailable'}</Text>} />
                <div className={styles.badges}>
                  {status && <Badge appearance={status === 'executed' ? 'tint' : status === 'failed' ? 'filled' : 'outline'}>{status.toUpperCase()}</Badge>}
                  {capability && <Badge appearance="outline">{capability}</Badge>}
                </div>
                {planId && <Text block size={200}>Plan: {planId}</Text>}
                {text(record, 'digest') && <Text block size={200} className={styles.muted}>Digest: {text(record, 'digest')}</Text>}
                {text(record, 'rendered_command') && <code className={styles.code}>{text(record, 'rendered_command')}</code>}
                {text(record, 'verification') && <Text block size={200}>Verification recorded</Text>}
              </Card>
            );
          })}
        </div>
        {!loading && filteredHistory.length === 0 && <Text className={styles.muted}>No durable mutation activity matches the current filter.</Text>}
      </section>
    </>
  );
}
