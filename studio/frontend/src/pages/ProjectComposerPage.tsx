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
  EventstreamDefinitionArtifact,
  MutationArtifactInput,
  ProjectPlan,
  ProjectPlanAction,
  ProjectTemplate,
  createMutationPlan,
  getEventstreamDefinitionArtifact,
  getProjectTemplates,
  planProject,
} from '../api/client';

type WorkspaceContext = { id: string; name: string };

type Props = {
  connected: boolean;
  workspaceContext: WorkspaceContext | null;
  onOpenChangePlans: () => void;
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

export function ProjectComposerPage({ connected, workspaceContext, onOpenChangePlans }: Props) {
  const styles = useStyles();
  const [templates, setTemplates] = useState<ProjectTemplate[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [plan, setPlan] = useState<ProjectPlan | null>(null);
  const [parameterValues, setParameterValues] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [planning, setPlanning] = useState(false);
  const [staging, setStaging] = useState(false);
  const [stagedItemIds, setStagedItemIds] = useState<string[]>([]);
  const [stagedReconciliationItemIds, setStagedReconciliationItemIds] = useState<string[]>([]);
  const [eventstreamArtifact, setEventstreamArtifact] = useState<EventstreamDefinitionArtifact | null>(null);
  const [artifactLoading, setArtifactLoading] = useState(false);
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
    setStagedItemIds([]);
    setStagedReconciliationItemIds([]);
    setEventstreamArtifact(null);
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

  const readyCreates = useMemo(
    () => (plan?.actions ?? []).filter(
      (action) => action.provisioning_ready && Boolean(action.provisioning_capability_id),
    ),
    [plan],
  );

  const unstagedReadyCreates = useMemo(
    () => readyCreates.filter((action) => !stagedItemIds.includes(action.item_id)),
    [readyCreates, stagedItemIds],
  );

  const readyReconciliations = useMemo(
    () => (plan?.actions ?? []).filter(
      (action) => action.reconciliation_ready && Boolean(action.reconciliation_capability_id),
    ),
    [plan],
  );

  const unstagedReadyReconciliations = useMemo(
    () => readyReconciliations.filter(
      (action) => !stagedReconciliationItemIds.includes(action.item_id),
    ),
    [readyReconciliations, stagedReconciliationItemIds],
  );


  async function handlePlan() {
    if (!template) return;
    setPlanning(true);
    setError('');
    try {
      const result = await planProject(template.id, workspaceContext?.id, parameterValues);
      setPlan(result);
      setStagedItemIds([]);
      setStagedReconciliationItemIds([]);
    } catch (err) {
      setPlan(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPlanning(false);
    }
  }

  async function handleStageReady() {
    if (!unstagedReadyCreates.length) return;
    setStaging(true);
    setError('');
    const staged: string[] = [];
    try {
      for (const action of unstagedReadyCreates) {
        if (!action.provisioning_capability_id) continue;
        let artifacts: MutationArtifactInput[] = [];
        if (action.item_type === 'Eventstream') {
          const artifact = await getEventstreamDefinitionArtifact(
            template.id,
            workspaceContext?.id,
            parameterValues,
          );
          setEventstreamArtifact(artifact);
          if (!artifact.ready) {
            throw new Error(
              `Eventstream definition is not ready: ${artifact.missing_requirements.join(', ')}`,
            );
          }
          artifacts = [{
            parameter: 'EventstreamPathDefinition',
            filename: artifact.filename,
            content: JSON.stringify(artifact.definition, null, 2),
          }];
        }

        await createMutationPlan(
          action.provisioning_capability_id,
          action.provisioning_parameters,
          artifacts,
        );
        staged.push(action.item_id);
      }
      setStagedItemIds((current) => Array.from(new Set([...current, ...staged])));
    } catch (err) {
      setStagedItemIds((current) => Array.from(new Set([...current, ...staged])));
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setStaging(false);
    }
  }

  async function handleStageReconciliations() {
    if (!template || !unstagedReadyReconciliations.length) return;
    setStaging(true);
    setError('');
    const staged: string[] = [];
    try {
      for (const action of unstagedReadyReconciliations) {
        if (!action.reconciliation_capability_id) continue;
        const artifact = await getEventstreamDefinitionArtifact(
          template.id,
          workspaceContext?.id,
          parameterValues,
        );
        setEventstreamArtifact(artifact);
        if (!artifact.ready) {
          throw new Error(
            `Eventstream definition is not ready: ${artifact.missing_requirements.join(', ')}`,
          );
        }
        await createMutationPlan(
          action.reconciliation_capability_id,
          action.reconciliation_parameters,
          [{
            parameter: 'EventstreamPathDefinition',
            filename: artifact.filename,
            content: JSON.stringify(artifact.definition, null, 2),
          }],
        );
        staged.push(action.item_id);
      }
      setStagedReconciliationItemIds((current) => Array.from(new Set([...current, ...staged])));
    } catch (err) {
      setStagedReconciliationItemIds((current) => Array.from(new Set([...current, ...staged])));
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setStaging(false);
    }
  }

  async function handleEventstreamArtifact() {
    if (!template) return;
    setArtifactLoading(true);
    setError('');
    try {
      const artifact = await getEventstreamDefinitionArtifact(template.id, workspaceContext?.id, parameterValues);
      setEventstreamArtifact(artifact);
    } catch (err) {
      setEventstreamArtifact(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setArtifactLoading(false);
    }
  }

  async function copyEventstreamDefinition() {
    if (!eventstreamArtifact) return;
    await navigator.clipboard.writeText(JSON.stringify(eventstreamArtifact.definition, null, 2));
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
          <Button appearance="secondary" disabled={artifactLoading || !workspaceContext || !connected} onClick={handleEventstreamArtifact}>
            {artifactLoading ? 'Rendering…' : 'Render eventstream.json'}
          </Button>
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

      {eventstreamArtifact && (
        <div className={styles.warning}>
          <Text weight="semibold">
            eventstream.json: {eventstreamArtifact.ready ? 'ready' : 'needs configuration'}
          </Text>
          <Text block>
            Source mode: {eventstreamArtifact.source_mode}. Schema: {eventstreamArtifact.provenance.schema}.
          </Text>
          {eventstreamArtifact.missing_requirements.length > 0 && (
            <Text block>Missing: {eventstreamArtifact.missing_requirements.join(', ')}</Text>
          )}
          <div className={styles.row}>
            <Button appearance="secondary" disabled={!eventstreamArtifact.ready} onClick={copyEventstreamDefinition}>
              Copy eventstream.json
            </Button>
          </div>
        </div>
      )}

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

      {plan && readyCreates.length > 0 && (
        <div className={styles.warning}>
          <Text weight="semibold">{readyCreates.length} create action(s) are dependency-ready.</Text>
          <Text block>Stage them as tenant-bound guarded change plans. This does not create anything yet.</Text>
          <div className={styles.row}>
            <Button
              appearance="primary"
              disabled={staging || unstagedReadyCreates.length === 0}
              onClick={handleStageReady}
            >
              {staging
                ? 'Staging…'
                : unstagedReadyCreates.length > 0
                  ? `Stage ${unstagedReadyCreates.length} ready create plan(s)`
                  : 'Ready creates staged'}
            </Button>
            {stagedItemIds.length > 0 && (
              <Button appearance="secondary" onClick={onOpenChangePlans}>Open Change Plans</Button>
            )}
          </div>
        </div>
      )}

      {plan && readyReconciliations.length > 0 && (
        <div className={styles.warning}>
          <Text weight="semibold">Existing Eventstream definition can be reconciled.</Text>
          <Text block>
            This stages a separate SHA-bound update plan; it does not execute the update directly.
          </Text>
          <div className={styles.row}>
            <Button
              appearance="primary"
              disabled={staging || unstagedReadyReconciliations.length === 0}
              onClick={handleStageReconciliations}
            >
              {staging
                ? 'Staging…'
                : unstagedReadyReconciliations.length > 0
                  ? `Stage ${unstagedReadyReconciliations.length} definition reconcile plan(s)`
                  : 'Definition reconcile staged'}
            </Button>
            {stagedReconciliationItemIds.length > 0 && (
              <Button appearance="secondary" onClick={onOpenChangePlans}>Open Change Plans</Button>
            )}
          </div>
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
                    {action?.provisioning_ready && <Badge appearance="tint">READY TO STAGE</Badge>}
                    {action?.reconciliation_ready && <Badge appearance="tint">READY TO RECONCILE</Badge>}
                    {action && stagedItemIds.includes(action.item_id) && <Badge appearance="filled">STAGED</Badge>}
                    {action && stagedReconciliationItemIds.includes(action.item_id) && <Badge appearance="filled">RECONCILE STAGED</Badge>}
                  </div>
                  {item.depends_on.length > 0 && (
                    <Text block size={200} className={styles.muted}>Depends on: {item.depends_on.join(', ')}</Text>
                  )}
                  {action && <Text block size={200}>{action.reason}</Text>}
                  {action?.provisioning_reason && <Text block size={200} className={styles.muted}>{action.provisioning_reason}</Text>}
                  {action?.reconciliation_reason && <Text block size={200} className={styles.muted}>{action.reconciliation_reason}</Text>}
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
        <Text weight="semibold">Execution stays guarded.</Text>
        <Text block>{plan?.apply_note ?? 'Run a plan first. Composer only stages reviewed change plans; execution happens in Change Plans.'}</Text>
      </div>
    </>
  );
}
