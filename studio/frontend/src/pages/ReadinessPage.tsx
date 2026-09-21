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
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BootstrapAction,
  ProjectReadinessCheck,
  ProjectReadinessReport,
  getProjectReadiness,
} from '../api/client';
import type { FabricProjectManifest } from '../data/project-contract.generated';

type ReadinessPageProps = {
  project: FabricProjectManifest;
  profileName: string;
  contextKey: string;
  onProfileChange: (profileName: string) => void;
};

const useStyles = makeStyles({
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '18px', marginBottom: '16px', flexWrap: 'wrap' },
  controls: { display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' },
  profileSelect: {
    minWidth: '150px',
    minHeight: '32px',
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorNeutralForeground1,
    padding: '0 8px',
  },
  stats: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '10px', margin: '16px 0' },
  stat: { padding: '14px' },
  grid: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(280px, 360px)', gap: '18px', alignItems: 'start' },
  checks: { display: 'grid', gap: '12px' },
  category: { display: 'grid', gap: '8px' },
  checkRow: { display: 'grid', gridTemplateColumns: 'minmax(180px, 0.8fr) 130px minmax(240px, 1.5fr)', gap: '12px', alignItems: 'start', padding: '10px 0', borderBottom: `1px solid ${tokens.colorNeutralStroke2}` },
  actions: { display: 'grid', gap: '10px' },
  action: { padding: '10px 0', borderBottom: `1px solid ${tokens.colorNeutralStroke2}` },
  source: { color: tokens.colorNeutralForeground3 },
  error: { color: tokens.colorPaletteRedForeground1 },
  warning: { padding: '10px 12px', border: `1px solid ${tokens.colorNeutralStroke2}`, borderRadius: tokens.borderRadiusMedium, marginBottom: '12px' },
  mono: { fontFamily: 'Consolas, monospace' },
});

function statusAppearance(status: ProjectReadinessCheck['status']) {
  if (status === 'satisfied') return 'tint' as const;
  if (status === 'blocked') return 'filled' as const;
  return 'outline' as const;
}

function statusLabel(status: ProjectReadinessCheck['status']) {
  return status.replace('_', ' ').toUpperCase();
}

function groupChecks(checks: ProjectReadinessCheck[]) {
  const groups = new Map<string, ProjectReadinessCheck[]>();
  for (const check of checks) {
    const current = groups.get(check.category) ?? [];
    current.push(check);
    groups.set(check.category, current);
  }
  return Array.from(groups.entries());
}

function ActionRow({ action }: { action: BootstrapAction }) {
  const styles = useStyles();
  return (
    <div className={styles.action}>
      <Text weight="semibold">{action.title}</Text>
      <Text block size={200}>Kind: {action.kind}</Text>
      <Text block size={200} className={styles.source}>{action.reason}</Text>
      <Badge appearance="outline">{action.executable ? 'EXECUTABLE' : 'PLAN ONLY'}</Badge>
    </div>
  );
}

export function ReadinessPage({
  project,
  profileName,
  contextKey,
  onProfileChange,
}: ReadinessPageProps) {
  const styles = useStyles();
  const [report, setReport] = useState<ProjectReadinessReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const next = await getProjectReadiness(project, profileName);
      setReport(next);
    } catch (err) {
      setReport(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [profileName, project]);

  useEffect(() => {
    void load();
  }, [contextKey, load]);

  const groups = useMemo(() => groupChecks(report?.checks ?? []), [report]);

  return (
    <>
      <div className={styles.header}>
        <div>
          <Title1>Readiness & Bootstrap</Title1>
          <Text block>{project.displayName}</Text>
          <Text block className={styles.source}>Evidence-first readiness. Local declarations are separated from backend session evidence and unknown tenant state.</Text>
        </div>
        <div className={styles.controls}>
          <label>
            <Text size={200}>Profile </Text>
            <select
              aria-label="Readiness profile"
              className={styles.profileSelect}
              value={profileName}
              onChange={(event) => onProfileChange(event.currentTarget.value)}
            >
              {Object.keys(project.profiles).map((name) => <option key={name} value={name}>{name.toUpperCase()}</option>)}
            </select>
          </label>
          <Button appearance="primary" disabled={loading} onClick={() => void load()}>Refresh readiness</Button>
        </div>
      </div>

      <div className={styles.warning}>
        <Text weight="semibold">M03 is non-executing.</Text>
        <Text block size={200}>Bootstrap actions are planning records only. UNKNOWN is never converted to MISSING, and no create/update call is made from this page.</Text>
      </div>

      {loading && <Spinner label="Evaluating project readiness" />}
      {error && <Text role="alert" block className={styles.error}>{error}</Text>}

      {report && (
        <>
          <div className={styles.stats}>
            <Card className={styles.stat}><Subtitle1>{report.counts.satisfied}</Subtitle1><Text>Satisfied checks</Text></Card>
            <Card className={styles.stat}><Subtitle1>{report.counts.unknown}</Subtitle1><Text>Unknown checks</Text></Card>
            <Card className={styles.stat}><Subtitle1>{report.counts.action_required}</Subtitle1><Text>Actions required</Text></Card>
            <Card className={styles.stat}><Subtitle1>{report.bootstrap_actions.length}</Subtitle1><Text>Planned bootstrap steps</Text></Card>
            <Card className={styles.stat}><Subtitle1>{report.authorization ? 'YES' : 'NO'}</Subtitle1><Text>Deployment authorized</Text></Card>
          </div>

          <Text block className={styles.source}>
            Target workspace: <span className={styles.mono}>{report.workspace_display_name}</span> · evaluated {report.evaluated_at}
          </Text>
          <Text block>{report.summary}</Text>

          <div className={styles.grid}>
            <section className={styles.checks} aria-label="Readiness checks">
              {groups.map(([category, checks]) => (
                <Card key={category}>
                  <CardHeader header={<Subtitle1>{category}</Subtitle1>} />
                  <div className={styles.category}>
                    {checks.map((check) => (
                      <div key={check.id} className={styles.checkRow}>
                        <div>
                          <Text weight="semibold">{check.title}</Text>
                          <Text block size={200}>{check.required ? 'Required' : 'Optional'}</Text>
                        </div>
                        <Badge appearance={statusAppearance(check.status)}>{statusLabel(check.status)}</Badge>
                        <div>
                          <Text block size={200}>{check.detail}</Text>
                          <Text block size={200} className={styles.source}>Evidence: {check.evidence_kind} · {check.source}</Text>
                          {check.next_action && <Text block size={200}>Next: {check.next_action}</Text>}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              ))}
            </section>

            <aside aria-label="Bootstrap plan">
              <Card>
                <CardHeader header={<Subtitle1>Bootstrap plan</Subtitle1>} description={<Text>Explicit next steps derived from unresolved readiness checks.</Text>} />
                <div className={styles.actions}>
                  {report.bootstrap_actions.map((action) => <ActionRow key={action.id} action={action} />)}
                  {report.bootstrap_actions.length === 0 && <Text className={styles.source}>No bootstrap steps proposed.</Text>}
                </div>
              </Card>
            </aside>
          </div>
        </>
      )}
    </>
  );
}
