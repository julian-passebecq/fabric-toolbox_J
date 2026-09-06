import {
  Badge,
  Button,
  Card,
  CardHeader,
  Subtitle1,
  Text,
  Title1,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import { useEffect, useState } from 'react';
import { Capability } from '../api/client';
import { CommandWorkbench } from '../components/CommandWorkbench';

const useStyles = makeStyles({
  header: { marginBottom: '18px' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '12px' },
  badges: { display: 'flex', gap: '8px', flexWrap: 'wrap', margin: '8px 0' },
  code: { display: 'block', padding: '8px 10px', margin: '8px 0', backgroundColor: tokens.colorNeutralBackground3, borderRadius: tokens.borderRadiusMedium, fontFamily: 'Consolas, monospace', overflowWrap: 'anywhere' },
  muted: { color: tokens.colorNeutralForeground3 },
});

type OperationsPageProps = {
  title: string;
  description: string;
  capabilities: Capability[];
  connected: boolean;
};

export function OperationsPage({ title, description, capabilities, connected }: OperationsPageProps) {
  const styles = useStyles();
  const [selected, setSelected] = useState<Capability | null>(capabilities[0] ?? null);

  useEffect(() => {
    if (!selected || !capabilities.some((capability) => capability.id === selected.id)) {
      setSelected(capabilities[0] ?? null);
    }
  }, [capabilities, selected]);

  return (
    <>
      <div className={styles.header}>
        <Title1>{title}</Title1>
        <Text block>{description}</Text>
      </div>

      <div className={styles.grid}>
        {capabilities.map((capability) => (
          <Card key={capability.id}>
            <CardHeader header={<Subtitle1>{capability.title}</Subtitle1>} description={<Text>{capability.description}</Text>} />
            <div className={styles.badges}>
              <Badge appearance="outline">{capability.provider}</Badge>
              <Badge appearance={capability.risk === 'read' ? 'tint' : 'outline'}>{capability.risk.toUpperCase()}</Badge>
              {capability.response_mode === 'fabric-lro' && <Badge appearance="tint">FABRIC LRO</Badge>}
              {capability.generated && <Badge appearance="ghost">AUTO-DISCOVERED</Badge>}
            </div>
            {capability.command && <code className={styles.code}>{capability.command}</code>}
            {capability.endpoint && <code className={styles.code}>{capability.endpoint}</code>}
            {capability.source_path && <Text block size={200} className={styles.muted}>{capability.source_path}</Text>}
            <Button appearance={selected?.id === capability.id ? 'primary' : 'secondary'} onClick={() => setSelected(capability)}>
              {selected?.id === capability.id ? 'Selected' : 'Open'}
            </Button>
          </Card>
        ))}
      </div>

      {selected && <CommandWorkbench capability={selected} connected={connected} />}
      {capabilities.length === 0 && <Text>No registered capability is available for this page.</Text>}
    </>
  );
}
