export type Risk = 'read' | 'write' | 'admin' | 'destructive';
export type ResponseMode = 'sync' | 'fabric-lro';
export type ExecutionPolicy = 'read' | 'guarded-write' | 'blocked';
export type MutationStatus = 'planned' | 'validated' | 'executing' | 'executed' | 'failed' | 'expired';

export type ParameterSpec = {
  name: string;
  type: string;
  mandatory: boolean;
  is_switch: boolean;
  description?: string;
  allowed_values: string[];
};

export type Capability = {
  id: string;
  title: string;
  category: string;
  provider: string;
  source: string;
  risk: Risk;
  response_mode?: ResponseMode;
  execution_policy?: ExecutionPolicy;
  supports_whatif?: boolean;
  verification_capability_id?: string;
  verification_parameter_map?: Record<string, string>;
  command?: string;
  endpoint?: string;
  description: string;
  source_path?: string;
  generated?: boolean;
  parameters?: string[];
  parameter_specs?: ParameterSpec[];
};

export type ExecutionPreview = {
  capability_id: string;
  provider: string;
  risk: Risk;
  command?: string;
  endpoint?: string;
  rendered_command?: string;
  transport?: string;
  executable: boolean;
  reason: string;
};

export type ExecutionResponse = {
  capability_id: string;
  provider: string;
  risk: Risk;
  rendered_command: string;
  result: Record<string, unknown>;
};

export type MutationPlan = {
  plan_id: string;
  capability_id: string;
  capability_title: string;
  provider: string;
  risk: Risk;
  tenant_id: string;
  parameters: Record<string, unknown>;
  rendered_command: string;
  validation_command?: string;
  supports_validation: boolean;
  confirmation_text: string;
  digest: string;
  created_at: string;
  expires_at: string;
  status: MutationStatus;
};

export type MutationValidationResponse = {
  plan: MutationPlan;
  result: Record<string, unknown>;
};

export type MutationExecutionResponse = {
  plan: MutationPlan;
  result: Record<string, unknown>;
  verification?: Record<string, unknown>;
};

export type SessionStatus = {
  mode: 'guarded-writes';
  transport: string;
  feature_provider: string;
  connected: boolean;
  tenant_id?: string;
};

export type SourceEntry = {
  id: string;
  name: string;
  origin: string;
  owner?: string;
  repository?: string;
  local_path?: string;
  integration?: string;
  update_strategy?: string;
  role?: string;
  feature_source?: boolean;
  execution_transport?: string;
  authentication_transport?: string;
  note?: string;
};

export type SourceRegistry = {
  schema_version: number;
  product: string;
  principles?: string[];
  sources: SourceEntry[];
  excluded_from_product_surface?: Array<{ id: string; reason: string }>;
};

export type SpecializedTool = {
  id: string;
  name: string;
  category: string;
  upstream_path: string;
  entrypoint: string;
  execution_kind: string;
  status: string;
  risk: Risk;
  description: string;
  prerequisites: string[];
  example: string;
  reason: string;
  available: boolean;
};

export type DiagnosticCheck = {
  name: string;
  ok: boolean;
  required: boolean;
  detail: string;
};

export type CompatibilityIssue = {
  severity: 'error' | 'warning';
  capability_id: string;
  message: string;
};

export type CompatibilityReport = {
  status: 'compatible' | 'incompatible';
  errors: number;
  warnings: number;
  duplicate_ids: string[];
  local_sources_checked: number;
  local_sources_missing: number;
  issues: CompatibilityIssue[];
};

export type Diagnostics = {
  status: 'ready' | 'degraded';
  platform: string;
  python: string;
  session: SessionStatus;
  catalog: {
    total: number;
    providers: Record<string, number>;
    risks: Record<string, number>;
    policies: Record<string, number>;
  };
  compatibility: CompatibilityReport;
  checks: DiagnosticCheck[];
};

export type ActivityRecord = Record<string, unknown> & { timestamp?: string; action?: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json() as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // keep HTTP status text
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function getCapabilities() {
  return request<Capability[]>('/api/capabilities');
}

export function getSession() {
  return request<SessionStatus>('/api/session');
}

export function connectFabric(tenantId: string) {
  return request<Record<string, unknown>>('/api/session/connect', {
    method: 'POST',
    body: JSON.stringify({ tenant_id: tenantId }),
  });
}

export function executeCapability(capabilityId: string, parameters: Record<string, unknown> = {}) {
  return request<ExecutionResponse>(`/api/capabilities/${encodeURIComponent(capabilityId)}/execute`, {
    method: 'POST',
    body: JSON.stringify({ parameters }),
  });
}

export function previewCapability(capabilityId: string, parameters: Record<string, unknown> = {}) {
  return request<ExecutionPreview>(`/api/capabilities/${encodeURIComponent(capabilityId)}/preview`, {
    method: 'POST',
    body: JSON.stringify({ parameters }),
  });
}

export function createMutationPlan(capabilityId: string, parameters: Record<string, unknown> = {}) {
  return request<MutationPlan>(`/api/capabilities/${encodeURIComponent(capabilityId)}/mutations/plan`, {
    method: 'POST',
    body: JSON.stringify({ parameters }),
  });
}

export function getMutationPlans() {
  return request<MutationPlan[]>('/api/mutations');
}

export function validateMutation(planId: string) {
  return request<MutationValidationResponse>(`/api/mutations/${encodeURIComponent(planId)}/validate`, {
    method: 'POST',
  });
}

export function executeMutation(planId: string, confirmation: string) {
  return request<MutationExecutionResponse>(`/api/mutations/${encodeURIComponent(planId)}/execute`, {
    method: 'POST',
    body: JSON.stringify({ confirmation }),
  });
}

export function getSources() {
  return request<SourceRegistry>('/api/sources');
}

export function getActivity(limit = 200) {
  return request<ActivityRecord[]>(`/api/activity?limit=${limit}`);
}

export function getSpecializedTools() {
  return request<SpecializedTool[]>('/api/tools');
}

export function getDiagnostics() {
  return request<Diagnostics>('/api/diagnostics');
}
