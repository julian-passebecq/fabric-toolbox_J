import {
  Badge,
  Button,
  Card,
  Checkbox,
  Field,
  Input,
  Spinner,
  Subtitle1,
  Text,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Capability,
  ExecutionPreview,
  MutationPlan,
  createMutationPlan,
  executeCapability,
  executeMutation,
  previewCapability,
  validateMutation,
} from '../api/client';
import { useRequestScope } from '../api/scope';
import { MutationOutcome } from './MutationOutcome';
import { ResultViewer } from './ResultViewer';

const useStyles = makeStyles({
  root: {
    marginTop: '18px',
    padding: '18px',
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
  },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' },
  badges: { display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '10px 0' },
  form: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '14px', marginTop: '18px' },
  actions: { display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '18px' },
  code: {
    display: 'block',
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere',
    padding: '12px',
    marginTop: '10px',
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: tokens.borderRadiusMedium,
    fontFamily: 'Consolas, monospace',
  },
  plan: {
    display: 'grid',
    gap: '10px',
    marginTop: '18px',
    padding: '16px',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  error: { color: tokens.colorPaletteRedForeground1, marginTop: '10px' },
  muted: { color: tokens.colorNeutralForeground3 },
  select: {
    width: '100%',
    minHeight: '32px',
    padding: '4px 8px',
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorNeutralForeground1,
  },
});

type CommandWorkbenchProps = {
  capability: Capability;
  connected: boolean;
  defaultParameters?: Record<string, string | boolean>;
  onClose?: () => void;
};

type BusyState = 'preview' | 'execute' | 'plan' | 'validate' | 'apply' | null;

export function CommandWorkbench({ capability, connected, defaultParameters = {}, onClose }: CommandWorkbenchProps) {
  const styles = useStyles();
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [preview, setPreview] = useState<ExecutionPreview | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [verification, setVerification] = useState<Record<string, unknown> | null>(null);
  const [mutationPlan, setMutationPlan] = useState<MutationPlan | null>(null);
  const [validationResult, setValidationResult] = useState<Record<string, unknown> | null>(null);
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<BusyState>(null);
  const defaultKey = JSON.stringify(defaultParameters);
  const capabilityKey = JSON.stringify([capability.id, capability.execution_policy, capability.parameter_specs]);
  const scope = useRequestScope(`${capabilityKey}:${defaultKey}:${connected}`);
  const inFlight = useRef(false);
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);

  useEffect(() => {
    const defaults: Record<string, string | boolean> = {};
    for (const spec of capability.parameter_specs ?? []) {
      const inherited = defaultParameters[spec.name];
      defaults[spec.name] = inherited !== undefined ? inherited : spec.is_switch ? false : '';
    }
    setValues(defaults);
    setPreview(null);
    setResult(null);
    setVerification(null);
    setMutationPlan(null);
    setValidationResult(null);
    setConfirmation('');
    setError('');
    setBusy(null);
    inFlight.current = false;
  }, [capabilityKey, defaultKey, connected]);

  const executableProvider = capability.provider === 'MicrosoftFabricMgmt' || capability.provider === 'Fabric REST API';
  const readExecutable = executableProvider && capability.risk === 'read' && capability.execution_policy === 'read';
  const guardedWrite = capability.provider === 'MicrosoftFabricMgmt'
    && capability.risk === 'write'
    && capability.execution_policy === 'guarded-write';
  const isLongRunning = capability.response_mode === 'fabric-lro';

  const requestParameters = useMemo(() => {
    const params: Record<string, unknown> = {};
    for (const [name, value] of Object.entries(values)) {
      if (typeof value === 'boolean') {
        if (value) params[name] = true;
      } else if (value.trim() !== '') {
        params[name] = value.trim();
      }
    }
    return params;
  }, [values]);

  function setParameter(name: string, value: string | boolean) {
    setValues((current) => ({ ...current, [name]: value }));
    setMutationPlan(null);
    setValidationResult(null);
    setConfirmation('');
    setResult(null);
    setVerification(null);
  }

  function validate(): string | null {
    for (const spec of capability.parameter_specs ?? []) {
      if (!spec.mandatory) continue;
      const value = values[spec.name];
      if (spec.is_switch) {
        if (value !== true) return `${spec.name} is required.`;
      } else if (typeof value !== 'string' || value.trim() === '') {
        return `${spec.name} is required.`;
      }
    }
    return null;
  }

  async function doPreview() {
    if (inFlight.current) return;
    const validation = validate();
    if (validation) {
      setError(validation);
      return;
    }
    inFlight.current = true;
    const active = scope.start();
    setBusy('preview');
    setError('');
    setResult(null);
    setVerification(null);
    try {
      const response = await previewCapability(capability.id, requestParameters);
      if (!active.current()) return;
      setPreview(response);
    } catch (err) {
      if (!active.current()) return;
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      active.finish();
      if (active.current()) { inFlight.current = false; setBusy(null); }
    }
  }

  async function doExecuteRead() {
    if (inFlight.current) return;
    const validation = validate();
    if (validation) {
      setError(validation);
      return;
    }
    inFlight.current = true;
    const active = scope.start();
    setBusy('execute');
    setError('');
    try {
      const response = await executeCapability(capability.id, requestParameters, active.signal);
      if (!active.current()) return;
      setPreview({
        capability_id: response.capability_id,
        provider: response.provider,
        risk: response.risk,
        command: capability.command,
        endpoint: capability.endpoint,
        rendered_command: response.rendered_command,
        executable: true,
        reason: isLongRunning
          ? 'Executed as a registered read-only operation; Fabric LRO completion was delegated to MicrosoftFabricMgmt.'
          : `Executed as a registered read-only ${capability.provider} operation.`,
      });
      setResult(response.result);
    } catch (err) {
      if (!active.current()) return;
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      active.finish();
      if (active.current()) { inFlight.current = false; setBusy(null); }
    }
  }

  async function doCreatePlan() {
    if (inFlight.current) return;
    const validation = validate();
    if (validation) {
      setError(validation);
      return;
    }
    inFlight.current = true;
    const active = scope.start();
    setBusy('plan');
    setError('');
    setResult(null);
    setVerification(null);
    setValidationResult(null);
    setConfirmation('');
    try {
      const response = await createMutationPlan(capability.id, requestParameters);
      if (!active.current()) return;
      setMutationPlan(response);
    } catch (err) {
      if (!active.current()) return;
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      active.finish();
      if (active.current()) { inFlight.current = false; setBusy(null); }
    }
  }

  async function doValidatePlan() {
    if (inFlight.current) return;
    if (!mutationPlan) return;
    inFlight.current = true;
    const active = scope.start();
    setBusy('validate');
    setError('');
    try {
      const response = await validateMutation(mutationPlan.plan_id);
      if (!active.current()) return;
      setMutationPlan(response.plan);
      setValidationResult(response.result);
    } catch (err) {
      if (!active.current()) return;
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      active.finish();
      if (active.current()) { inFlight.current = false; setBusy(null); }
    }
  }

  async function doApplyPlan() {
    if (inFlight.current) return;
    if (!mutationPlan || !applyReady) return;
    inFlight.current = true;
    const active = scope.start();
    setMutationPlan({ ...mutationPlan, status: 'executing' });
    setBusy('apply');
    setError('');
    try {
      const response = await executeMutation(mutationPlan.plan_id, confirmation);
      if (!active.current()) return;
      setMutationPlan(response.plan);
      setResult(response.result);
      setVerification(response.verification ?? null);
    } catch (err) {
      if (!active.current()) return;
      setMutationPlan({ ...mutationPlan, status: 'outcome_unknown' });
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      active.finish();
      if (active.current()) { inFlight.current = false; setBusy(null); }
    }
  }

  async function copyRendered() {
    const command = mutationPlan?.rendered_command ?? preview?.rendered_command ?? capability.command ?? capability.endpoint;
    if (command) await navigator.clipboard.writeText(command);
  }

  const applyReady = Boolean(
    mutationPlan
    && mutationPlan.status === 'validated'
    && confirmation === mutationPlan.confirmation_text
    && Date.parse(mutationPlan.expires_at) > now
    && connected,
  );

  return (
    <section className={styles.root}>
      <div className={styles.header}>
        <div>
          <Subtitle1>{capability.title}</Subtitle1>
          <Text block>{capability.description}</Text>
        </div>
        {onClose && <Button appearance="subtle" onClick={onClose}>Close</Button>}
      </div>

      <div className={styles.badges}>
        <Badge appearance="outline">Feature provider: {capability.provider}</Badge>
        <Badge appearance="outline">Source: {capability.source}</Badge>
        <Badge appearance={capability.risk === 'read' ? 'tint' : 'outline'}>{capability.risk.toUpperCase()}</Badge>
        {capability.execution_policy && <Badge appearance="outline">{capability.execution_policy.toUpperCase()}</Badge>}
        {capability.supports_whatif && <Badge appearance="tint">UPSTREAM WHATIF</Badge>}
        {isLongRunning && <Badge appearance="tint">FABRIC LRO</Badge>}
        {capability.generated && <Badge appearance="ghost">AUTO-DISCOVERED</Badge>}
      </div>

      {capability.source_path && <Text block className={styles.muted}>{capability.source_path}</Text>}
      {capability.command && <code className={styles.code}>{capability.command}</code>}
      {capability.endpoint && <code className={styles.code}>{capability.endpoint}</code>}

      {(capability.parameter_specs ?? []).length > 0 && (
        <div className={styles.form}>
          {(capability.parameter_specs ?? []).map((spec) => (
            <div key={spec.name}>
              {spec.is_switch ? (
                <Checkbox
                  disabled={busy !== null}
                  checked={values[spec.name] === true}
                  label={`${spec.name}${spec.mandatory ? ' *' : ''}`}
                  onChange={(_, data) => setParameter(spec.name, data.checked === true)}
                />
              ) : spec.allowed_values.length > 0 ? (
                <Field label={`${spec.name}${spec.mandatory ? ' *' : ''}`} hint={spec.description}>
                  <select
                    disabled={busy !== null}
                    className={styles.select}
                    value={String(values[spec.name] ?? '')}
                    onChange={(event) => setParameter(spec.name, event.target.value)}
                  >
                    <option value="">Select…</option>
                    {spec.allowed_values.map((option) => <option key={option} value={option}>{option}</option>)}
                  </select>
                </Field>
              ) : (
                <Field label={`${spec.name}${spec.mandatory ? ' *' : ''}`} hint={spec.description ?? `Parameter type: ${spec.type}`}>
                  <Input
                    disabled={busy !== null}
                    value={String(values[spec.name] ?? '')}
                    onChange={(_, data) => setParameter(spec.name, data.value)}
                  />
                </Field>
              )}
            </div>
          ))}
        </div>
      )}

      {!readExecutable && !guardedWrite && (
        <Card>
          <Text>{capability.blocked_reason ?? 'This capability is catalogued for reference but remains blocked by Studio execution policy.'}</Text>
        </Card>
      )}

      <div className={styles.actions}>
        <Button disabled={busy !== null} onClick={doPreview}>{busy === 'preview' ? 'Previewing…' : 'Preview PowerShell'}</Button>
        {readExecutable && (
          <Button appearance="primary" disabled={!connected || busy !== null} onClick={doExecuteRead}>
            {busy === 'execute' ? (isLongRunning ? 'Waiting for Fabric…' : 'Running…') : 'Run read-only'}
          </Button>
        )}
        {guardedWrite && (
          <Button appearance="primary" disabled={!connected || busy !== null} onClick={doCreatePlan}>
            {busy === 'plan' ? 'Creating plan…' : mutationPlan ? 'Recreate plan' : 'Create guarded plan'}
          </Button>
        )}
        <Button disabled={!preview?.rendered_command && !mutationPlan?.rendered_command && !capability.command && !capability.endpoint} onClick={copyRendered}>Copy</Button>
      </div>

      {!connected && (readExecutable || guardedWrite) && <Text block className={styles.muted}>Connect to a Fabric tenant before execution. Command preview remains available offline.</Text>}
      {busy && <Spinner size="tiny" label={busy === 'preview' ? 'Rendering command' : busy === 'validate' ? 'Running upstream -WhatIf' : busy === 'apply' ? 'Applying guarded mutation' : busy === 'plan' ? 'Creating tenant-bound mutation plan' : isLongRunning ? 'Waiting for Fabric operation completion' : 'Executing command'} />}
      {error && <Text role="alert" block className={styles.error}>{error}</Text>}

      {preview && (
        <div>
          <Text block weight="semibold">Execution preview</Text>
          {preview.rendered_command && <code className={styles.code}>{preview.rendered_command}</code>}
          <Text block className={styles.muted}>{preview.reason}</Text>
          {preview.transport && <Text block className={styles.muted}>Transport: {preview.transport}</Text>}
        </div>
      )}

      {mutationPlan && (
        <div className={styles.plan}>
          <div className={styles.badges}>
            <Badge appearance="filled">PLAN {mutationPlan.plan_id.slice(0, 8).toUpperCase()}</Badge>
            <Badge appearance="outline">{mutationPlan.status.toUpperCase()}</Badge>
            <Badge appearance="outline">Tenant-bound</Badge>
            <Badge appearance="outline">Single use</Badge>
          </div>
          <Text block weight="semibold">Immutable mutation plan</Text>
          <MutationOutcome status={mutationPlan.status} />
          {mutationPlan.audit_warning && <p role="alert">{mutationPlan.audit_warning}</p>}
          <Text block className={styles.muted}>Expires: {new Date(mutationPlan.expires_at).toLocaleString()}</Text>
          <Text block className={styles.muted}>SHA-256: {mutationPlan.digest}</Text>
          <code className={styles.code}>{mutationPlan.rendered_command}</code>
          {mutationPlan.validation_command && (
            <>
              <Text block weight="semibold">Upstream validation command</Text>
              <code className={styles.code}>{mutationPlan.validation_command}</code>
            </>
          )}
          <div className={styles.actions}>
            {mutationPlan.supports_validation && (
              <Button disabled={!connected || busy !== null || mutationPlan.status !== 'planned' || Date.parse(mutationPlan.expires_at) <= now} onClick={doValidatePlan}>
                {busy === 'validate' ? 'Validating…' : 'Validate with -WhatIf'}
              </Button>
            )}
          </div>
          {validationResult && <ResultViewer result={validationResult} fileName={`fabric-${capability.id}-whatif.json`} />}
          <Field
            label={`Type ${mutationPlan.confirmation_text} to apply`}
            hint="The broker checks this exact text, current tenant, plan expiry and validation status before execution."
          >
            <Input value={confirmation} onChange={(_, data) => setConfirmation(data.value)} />
          </Field>
          <Button appearance="primary" disabled={!applyReady || busy !== null} onClick={doApplyPlan}>
            {busy === 'apply' ? 'Applying…' : 'Apply guarded write'}
          </Button>
        </div>
      )}

      {result && <ResultViewer result={result} fileName={`fabric-${capability.id}.json`} />}
      {verification && (
        <div>
          <Text block weight="semibold">Read-back verification</Text>
          <ResultViewer result={verification} fileName={`fabric-${capability.id}-verification.json`} />
        </div>
      )}
    </section>
  );
}
