import {
  Badge,
  Button,
  Card,
  CardHeader,
  Divider,
  Input,
  Spinner,
  Subtitle1,
  Text,
  Title1,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useEffect, useMemo, useState } from 'react';
import {
  ProjectPlan,
  ProjectPlanAction,
  ProjectTemplate,
  getProjectTemplates,
  planProject,
} from '../api/client';

type WorkspaceContext = { id: string; name: string };

type Props = {
  connected: boolean;
  workspaceContext: WorkspaceContext | null;
};

const useStyles = makeStyles({
  hero: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '24px', marginBottom: '20px' },
  cards: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: '14px', marginTop: '16px' },
  stats: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px', margin: '16px 0' },
  stat: { padding: '14px' },
  row: { display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginTop: '8px' },
  muted: { color: tokens.colorNeutralForeground3 },
  warning: { padding: '12px', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, marginTop: '14px' },
  section: { marginTop: '28px' },
});

function actionAppearance(action?: ProjectPlanAction['action']) {
  if (action === 'unchanged') return 'tint';
  if (action === 'conflict') return 'filled';
  return 'outline';
}

export function ProjectComposerPage({ connected, workspaceContext }: Props) {
  const styles = useStyles();
  const [templates, setTemplates] = useState<ProjectTemplate[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [plan, setPlan] = useState<ProjectPlan | null>(null);
  const [parameterValues, setParameterValues] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [planning, setPlanning] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    getProjectTemplates()
      .then((items) => {
        if (cancelled) return;
        setTemplates(items);
        if (items.length) setSelectedId(items[0].id);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const template = useMemo(
    () => templates.find((item) => item.id === selectedId) ?? templates[0],
    [templates, selectedId],
  );

  useEffect(() => {
    if (!template) return;
    const defaults: Record<string, unknown> = {};
    for (const parameter of template.parameters) {
      defaults[parameter.name] = parameter.default ?? '';
    }
    setParameterValues(defaults);
    setPlan(null);
  }, [template]);

  const planById = useMemo(() => {
    const map = new Map<string, ProjectPlanAction>();
    for (const action of plan?.actions ?? []) map.set(action.item_id, action);
    return map;
  }, [plan]);

  const areas = useMemo(() => {
    if (!template) return [];
    return Array.from(new Set(template.items.map((item) => item.area)));
  }, [template]);

  async function handlePlan() {
    if (!template) return;
    setPlanning(true);
    setError('');
    try {
      const result = await planProject(template.id, workspaceContext?.id, parameterValues);
      setPlan(result);
    } catch (err) {
      setPlan(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPlanning(false);
    }
  }

  async function copyVsCodeHandoff() {
    if (!template) return;
    const safeParameters = Object.fromEntries(
      template.parameters.map((parameter) => [
        parameter.name,
        parameter.secret && parameterValues[parameter.name] ? '***' : (plan?.resolved_parameters[parameter.name] ?? parameterValues[parameter.name]),
      ]),
    );
    const handoff = {
      project: template.id,
      workspace: workspaceContext ?? { name: template.workspace_name },
      parameters: safeParameters,
      authoring_items: template.items
        .filter((item) => item.vscode_handoff)
        .map((item) => ({ type: item.type, displayName: item.display_name, settings: item.settings })),
    };
    await navigator.clipboard.writeText(JSON.stringify(handoff, null, 2));
  }

  if (loading) return <Spinner label="Loading Fabric project templates" />;
  if (!template) return <Text>No project templates are registered.</Text>;

  const canLivePlan = !workspaceContext || connected;

  return (
    <>
      <div className={styles.hero}>
        <div>
          <Title1>Project Composer</Title1>
          <Text block>Declare a Fabric architecture, compare it with a live workspace and prepare a guarded deployment plan.</Text>
          <div className={styles.row}>
            <Badge appearance="filled">{template.name}</Badge>
            <Badge appearance="outline">Template {template.version}</Badge>
            <Badge appearance="outline">{template.items.length} managed items</Badge>
          </div>
        </div>
        <div className={styles.row}>
          <Button appearance="primary" disabled={planning || !canLivePlan} onClick={handlePlan}>
            {planning ? 'Planning…' : workspaceContext ? 'Plan against selected workspace' : 'Plan new workspace'}
          </Button>
          <Button appearance="secondary" onClick={copyVsCodeHandoff}>Copy VS Code handoff</Button>
        </div>
      </div>

      {templates.length > 1 && (
        <div className={styles.row}>
          {templates.map((item) => (
            <Button
              key={item.id}
              appearance={item.id === template.id ? 'primary' : 'secondary'}
              onClick={() => { setSelectedId(item.id); setPlan(null); }}
            >
              {item.name}
            </Button>
          ))}
        </div>
      )}

      <Card>
        <CardHeader
          header={<Subtitle1>{workspaceContext ? 'Existing workspace target' : 'New workspace target'}</Subtitle1>}
          description={<Text>{workspaceContext ? workspaceContext.name : template.workspace_name}</Text>}
        />
        <Text>{template.description}</Text>
        <div className={styles.row}>
          {template.tags.map((tag) => <Badge key={tag} appearance="outline">{tag}</Badge>)}
        </div>
      </Card>

      <section className={styles.section}>
        <Subtitle1>Project parameters</Subtitle1>
        <Text block className={styles.muted}>Values are used for planning and VS Code handoff. Secrets are redacted by the backend plan response.</Text>
        <div className={styles.cards}>
          {template.parameters.map((parameter) => (
            <Card key={parameter.name}>
              <CardHeader
                header={<Subtitle1>{parameter.label}</Subtitle1>}
                description={<Text>{parameter.description}</Text>}
              />
              <Input
                type={parameter.secret ? 'password' : 'text'}
                value={String(parameterValues[parameter.name] ?? '')}
                onChange={(_, data) => setParameterValues((current) => ({ ...current, [parameter.name]: data.value }))}
                placeholder={parameter.required ? 'Required' : 'Optional'}
              />
              <div className={styles.row}>
                <Badge appearance={parameter.required ? 'tint' : 'outline'}>{parameter.required ? 'REQUIRED' : 'OPTIONAL'}</Badge>
                {parameter.allowed_values.length > 0 && <Text size={200}>Allowed: {parameter.allowed_values.join(', ')}</Text>}
              </div>
            </Card>
          ))}
        </div>
      </section>

      {!canLivePlan && (
        <div className={styles.warning}>
          <Text weight="semibold">Connect to the Fabric tenant before diffing the selected live workspace.</Text>
        </div>
      )}
      {error && <div className={styles.warning}><Text>{error}</Text></div>}

      {plan && plan.missing_parameters.length > 0 && (
        <div className={styles.warning}>
          <Text weight="semibold">Missing required parameters: {plan.missing_parameters.join(', ')}</Text>
        </div>
      )}

      {plan && (
        <div className={styles.stats}>
          {[
            ['Create', plan.counts.create ?? 0],
            ['Unchanged', plan.counts.unchanged ?? 0],
            ['Conflicts', plan.counts.conflict ?? 0],
            ['Unmanaged', plan.counts.unmanaged ?? 0],
          ].map(([label, value]) => (
            <Card key={String(label)} className={styles.stat}>
              <Subtitle1>{String(value)}</Subtitle1>
              <Text>{String(label)}</Text>
            </Card>
          ))}
        </div>
      )}

      {areas.map((area) => (
        <section key={area} className={styles.section}>
          <Subtitle1>{area}</Subtitle1>
          <Divider />
          <div className={styles.cards}>
            {template.items.filter((item) => item.area === area).map((item) => {
              const action = planById.get(item.id);
              return (
                <Card key={item.id}>
                  <CardHeader
                    header={<Subtitle1>{item.display_name}</Subtitle1>}
                    description={<Text>{item.description}</Text>}
                  />
                  <div className={styles.row}>
                    <Badge appearance="outline">{item.type}</Badge>
                    <Badge appearance="outline">{item.definition_strategy}</Badge>
                    {item.vscode_handoff && <Badge appearance="tint">VS CODE</Badge>}
                    {action && <Badge appearance={actionAppearance(action.action)}>{action.action.toUpperCase()}</Badge>}
                  </div>
                  {item.depends_on.length > 0 && (
                    <Text block size={200} className={styles.muted}>Depends on: {item.depends_on.join(', ')}</Text>
                  )}
                  {action && <Text block size={200}>{action.reason}</Text>}
                </Card>
              );
            })}
          </div>
        </section>
      ))}

      {plan && plan.actions.some((item) => item.action === 'unmanaged') && (
        <section className={styles.section}>
          <Subtitle1>Existing unmanaged items</Subtitle1>
          <Divider />
          <div className={styles.cards}>
            {plan.actions.filter((item) => item.action === 'unmanaged').map((item) => (
              <Card key={item.item_id}>
                <CardHeader header={<Subtitle1>{item.display_name}</Subtitle1>} description={<Text>{item.reason}</Text>} />
                <Badge appearance="outline">{item.item_type}</Badge>
              </Card>
            ))}
          </div>
        </section>
      )}

      <div className={styles.warning}>
        <Text weight="semibold">Apply is still gated.</Text>
        <Text block>{plan?.apply_note ?? 'Run a plan first. The current milestone does not broaden the guarded-write allowlist.'}</Text>
      </div>
    </>
  );
}
