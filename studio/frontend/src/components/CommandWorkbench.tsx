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
import { useEffect, useMemo, useState } from 'react';
import {
  Capability,
  ExecutionPreview,
  executeCapability,
  previewCapability,
} from '../api/client';

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
  result: {
    maxHeight: '360px',
    overflow: 'auto',
    padding: '12px',
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: tokens.borderRadiusMedium,
    fontFamily: 'Consolas, monospace',
    fontSize: '12px',
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

export function CommandWorkbench({ capability, connected, defaultParameters = {}, onClose }: CommandWorkbenchProps) {
  const styles = useStyles();
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [preview, setPreview] = useState<ExecutionPreview | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<'preview' | 'execute' | null>(null);
  const defaultKey = JSON.stringify(defaultParameters);

  useEffect(() => {
    const defaults: Record<string, string | boolean> = {};
    for (const spec of capability.parameter_specs ?? []) {
      const inherited = defaultParameters[spec.name];
      defaults[spec.name] = inherited !== undefined ? inherited : spec.is_switch ? false : '';
    }
    setValues(defaults);
    setPreview(null);
    setResult(null);
    setError('');
  }, [capability.id, defaultKey]);

  const executableProvider = capability.provider === 'MicrosoftFabricMgmt' || capability.provider === 'Fabric REST API';
  const executable = executableProvider && capability.risk === 'read';
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
    const validation = validate();
    if (validation) {
      setError(validation);
      return;
    }
    setBusy('preview');
    setError('');
    setResult(null);
    try {
      setPreview(await previewCapability(capability.id, requestParameters));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function doExecute() {
    const validation = validate();
    if (validation) {
      setError(validation);
      return;
    }
    setBusy('execute');
    setError('');
    try {
      const response = await executeCapability(capability.id, requestParameters);
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
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function copyRendered() {
    const command = preview?.rendered_command ?? capability.command ?? capability.endpoint;
    if (command) await navigator.clipboard.writeText(command);
  }

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
                  checked={values[spec.name] === true}
                  label={`${spec.name}${spec.mandatory ? ' *' : ''}`}
                  onChange={(_, data) => setValues((current) => ({ ...current, [spec.name]: data.checked === true }))}
                />
              ) : spec.allowed_values.length > 0 ? (
                <Field label={`${spec.name}${spec.mandatory ? ' *' : ''}`} hint={spec.description}>
                  <select
                    className={styles.select}
                    value={String(values[spec.name] ?? '')}
                    onChange={(event) => setValues((current) => ({ ...current, [spec.name]: event.target.value }))}
                  >
                    <option value="">Select…</option>
                    {spec.allowed_values.map((option) => <option key={option} value={option}>{option}</option>)}
                  </select>
                </Field>
              ) : (
                <Field label={`${spec.name}${spec.mandatory ? ' *' : ''}`} hint={spec.description ?? `Parameter type: ${spec.type}`}>
                  <Input
                    value={String(values[spec.name] ?? '')}
                    onChange={(_, data) => setValues((current) => ({ ...current, [spec.name]: data.value }))}
                  />
                </Field>
              )}
            </div>
          ))}
        </div>
      )}

      {!executable && (
        <Card>
          <Text>This capability is catalogued for reference but is blocked by the current read-only execution policy.</Text>
        </Card>
      )}

      <div className={styles.actions}>
        <Button disabled={busy !== null} onClick={doPreview}>{busy === 'preview' ? 'Previewing…' : 'Preview PowerShell'}</Button>
        <Button appearance="primary" disabled={!executable || !connected || busy !== null} onClick={doExecute}>
          {busy === 'execute' ? (isLongRunning ? 'Waiting for Fabric…' : 'Running…') : 'Run read-only'}
        </Button>
        <Button disabled={!preview?.rendered_command && !capability.command && !capability.endpoint} onClick={copyRendered}>Copy</Button>
      </div>

      {!connected && executable && <Text block className={styles.muted}>Connect to a Fabric tenant before execution. Preview remains available offline.</Text>}
      {busy && <Spinner size="tiny" label={busy === 'preview' ? 'Rendering command' : isLongRunning ? 'Waiting for Fabric operation completion' : 'Executing command'} />}
      {error && <Text block className={styles.error}>{error}</Text>}

      {preview && (
        <div>
          <Text block weight="semibold">Execution preview</Text>
          {preview.rendered_command && <code className={styles.code}>{preview.rendered_command}</code>}
          <Text block className={styles.muted}>{preview.reason}</Text>
          {preview.transport && <Text block className={styles.muted}>Transport: {preview.transport}</Text>}
        </div>
      )}

      {result && (
        <div>
          <Text block weight="semibold">Result</Text>
          <pre className={styles.result}>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}
