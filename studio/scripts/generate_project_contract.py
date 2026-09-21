"""Generate the frontend Fabric project manifest types from the canonical schema."""
from __future__ import annotations

import json
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = STUDIO_ROOT / "contracts" / "project.schema.json"
OUTPUT = STUDIO_ROOT / "frontend" / "src" / "data" / "project-contract.generated.ts"


def _quoted(values: list[str]) -> str:
    return " | ".join(json.dumps(value) for value in values)


def render(schema: dict) -> str:
    props = schema["properties"]
    profile = props["profiles"]["additionalProperties"]["properties"]
    resource = props["resources"]["items"]["properties"]
    flow = props["dataFlows"]["items"]["properties"]
    types = resource["type"]["enum"]
    owners = profile["deploymentOwner"]["enum"]
    management = resource["management"]["enum"]
    flow_kinds = flow["kind"]["enum"]
    version = props["schemaVersion"]["const"]
    mode = props["mode"]["const"]
    evidence = flow["evidence"]["const"]
    return f'''// Generated from studio/contracts/project.schema.json. Do not edit by hand.

export const PROJECT_SCHEMA_VERSION = {json.dumps(version)} as const;
export const PROJECT_RESOURCE_TYPES = {json.dumps(types)} as const;
export const PROJECT_DEPLOYMENT_OWNERS = {json.dumps(owners)} as const;

export type ProjectMode = {json.dumps(mode)};
export type ProjectResourceType = {_quoted(types)};
export type ProjectDeploymentOwner = {_quoted(owners)};
export type ProjectManagement = {_quoted(management)};
export type ProjectDataFlowKind = {_quoted(flow_kinds)};

export interface FabricProjectProfile {{
  workspaceDisplayName: string;
  capacityRef: string;
  identityRef: string;
  deploymentOwner: ProjectDeploymentOwner;
}}

export interface FabricProjectResource {{
  key: string;
  type: ProjectResourceType;
  displayName: string;
  definitionPath: string;
  management: ProjectManagement;
  dependsOn: string[];
}}

export interface FabricProjectDataFlow {{
  from: string;
  to: string;
  kind: ProjectDataFlowKind;
  evidence: {json.dumps(evidence)};
}}

export interface FabricProjectTelemetry {{
  sourceConnectionRef: string;
  eventIdField: string;
  eventTimeField: string;
  freshnessTargetSeconds: number;
}}

export interface FabricProjectManifest {{
  schemaVersion: typeof PROJECT_SCHEMA_VERSION;
  mode: ProjectMode;
  projectId: string;
  displayName: string;
  profiles: Record<string, FabricProjectProfile>;
  resources: FabricProjectResource[];
  dataFlows: FabricProjectDataFlow[];
  telemetry?: FabricProjectTelemetry;
}}
'''


def main() -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    OUTPUT.write_text(render(schema), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
