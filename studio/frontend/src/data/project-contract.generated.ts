// Generated from studio/contracts/project.schema.json. Do not edit by hand.

export const PROJECT_SCHEMA_VERSION = "1.0-draft" as const;
export const PROJECT_RESOURCE_TYPES = ["Lakehouse", "Notebook", "Environment", "Eventhouse", "KQLDatabase", "Eventstream", "KQLDashboard", "VariableLibrary", "Reflex"] as const;
export const PROJECT_DEPLOYMENT_OWNERS = ["studio-runner", "native-git"] as const;

export type ProjectMode = "design_only";
export type ProjectResourceType = "Lakehouse" | "Notebook" | "Environment" | "Eventhouse" | "KQLDatabase" | "Eventstream" | "KQLDashboard" | "VariableLibrary" | "Reflex";
export type ProjectDeploymentOwner = "studio-runner" | "native-git";
export type ProjectManagement = "managed" | "external";
export type ProjectDataFlowKind = "events" | "query" | "batch" | "analytical-exposure";

export interface FabricProjectProfile {
  workspaceDisplayName: string;
  capacityRef: string;
  identityRef: string;
  deploymentOwner: ProjectDeploymentOwner;
}

export interface FabricProjectResource {
  key: string;
  type: ProjectResourceType;
  displayName: string;
  definitionPath: string;
  management: ProjectManagement;
  dependsOn: string[];
}

export interface FabricProjectDataFlow {
  from: string;
  to: string;
  kind: ProjectDataFlowKind;
  evidence: "declared";
}

export interface FabricProjectTelemetry {
  sourceConnectionRef: string;
  eventIdField: string;
  eventTimeField: string;
  freshnessTargetSeconds: number;
}

export interface FabricProjectManifest {
  schemaVersion: typeof PROJECT_SCHEMA_VERSION;
  mode: ProjectMode;
  projectId: string;
  displayName: string;
  profiles: Record<string, FabricProjectProfile>;
  resources: FabricProjectResource[];
  dataFlows: FabricProjectDataFlow[];
  telemetry?: FabricProjectTelemetry;
}
