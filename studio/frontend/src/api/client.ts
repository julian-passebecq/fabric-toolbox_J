export type Risk = 'read' | 'write' | 'admin' | 'destructive';

export type Capability = {
  id: string;
  title: string;
  category: string;
  provider: string;
  source: string;
  risk: Risk;
  command?: string;
  endpoint?: string;
  description: string;
  source_path?: string;
  generated?: boolean;
  parameters?: string[];
};

export type ExecutionResponse = {
  capability_id: string;
  provider: string;
  risk: Risk;
  rendered_command: string;
  result: Record<string, unknown>;
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
  note?: string;
};

export type SourceRegistry = {
  schema_version: number;
  product: string;
  principles?: string[];
  sources: SourceEntry[];
  excluded_from_product_surface?: Array<{ id: string; reason: string }>;
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
  return request<Record<string, unknown>>(`/api/capabilities/${encodeURIComponent(capabilityId)}/preview`, {
    method: 'POST',
    body: JSON.stringify({ parameters }),
  });
}

export function getSources() {
  return request<SourceRegistry>('/api/sources');
}

export function getActivity(limit = 200) {
  return request<ActivityRecord[]>(`/api/activity?limit=${limit}`);
}
