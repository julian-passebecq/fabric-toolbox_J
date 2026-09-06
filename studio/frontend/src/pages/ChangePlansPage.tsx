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
import { useEffect, useState } from 'react';
import { MutationPlan, getMutationPlans } from '../api/client';

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', marginBottom: '18px' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '12px' },
  badges: { display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '8px 0' },
  code: { display: 'block', padding: '8px 10px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  muted: { color: tokens.colorNeutralForeground3 },
  error: { color: tokens.colorPaletteRedForeground1 },
});

function statusAppearance(status: MutationPlan['status']) {
  if (status === 'executed' || status === 'validated') return 'tint';
  if (status === 'failed' || status === 'expired') return 'filled';
  return 'outline';
}

export function ChangePlansPage() {
  const styles = useStyles();
  const [plans, setPlans] = useState<MutationPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      setPlans(await getMutationPlans());
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
          <Title1>Change Plans</Title1>
          <Text block>Review mutation plans held by the current Studio backend session. Plans are tenant-bound, expire after ten minutes and are single use.</Text>
        </div>
        <Button onClick={() => void load()} disabled={loading}>Refresh</Button>
      </div>

      {loading && <Spinner label="Loading mutation plans" />}
      {error && <Text block className={styles.error}>{error}</Text>}
      {!loading && !error && plans.length === 0 && <Text className={styles.muted}>No mutation plans exist in this backend session.</Text>}

      <div className={styles.grid}>
        {plans.map((plan) => (
          <Card key={plan.plan_id}>
            <CardHeader
              header={<Subtitle1>{plan.capability_title}</Subtitle1>}
              description={<Text>Plan {plan.plan_id.slice(0, 8).toUpperCase()}</Text>}
            />
            <div className={styles.badges}>
              <Badge appearance={statusAppearance(plan.status)}>{plan.status.toUpperCase()}</Badge>
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
    </>
  );
}
