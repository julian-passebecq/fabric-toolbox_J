import type { FabricProjectManifest } from './project-contract.generated';

// UI seed derived from studio/examples/fabric-project/foil.project.json.
// It is illustrative desired state only: it carries no live Fabric IDs or health evidence.
export const ILLUSTRATIVE_FOIL_PROJECT: FabricProjectManifest = {
  schemaVersion: '1.0-draft',
  mode: 'design_only',
  projectId: 'foil',
  displayName: 'Foil telemetry - illustrative configuration',
  profiles: {
    dev: {
      workspaceDisplayName: 'foil-dev',
      capacityRef: 'binding:capacity/dev',
      identityRef: 'auth:operator',
      deploymentOwner: 'studio-runner',
    },
    test: {
      workspaceDisplayName: 'foil-test',
      capacityRef: 'binding:capacity/test',
      identityRef: 'auth:release-test',
      deploymentOwner: 'studio-runner',
    },
    prod: {
      workspaceDisplayName: 'foil-prod',
      capacityRef: 'binding:capacity/prod',
      identityRef: 'auth:release-prod',
      deploymentOwner: 'studio-runner',
    },
  },
  resources: [
    { key: 'eventhouse', type: 'Eventhouse', displayName: 'FoilEvents', definitionPath: 'fabric/FoilEvents.Eventhouse', management: 'managed', dependsOn: [] },
    { key: 'telemetry_db', type: 'KQLDatabase', displayName: 'FoilTelemetryDb', definitionPath: 'fabric/FoilTelemetryDb.KQLDatabase', management: 'managed', dependsOn: ['eventhouse'] },
    { key: 'telemetry_stream', type: 'Eventstream', displayName: 'FoilTelemetryStream', definitionPath: 'fabric/FoilTelemetryStream.Eventstream', management: 'managed', dependsOn: ['telemetry_db'] },
    { key: 'realtime_dashboard', type: 'KQLDashboard', displayName: 'FoilRealtime', definitionPath: 'fabric/FoilRealtime.KQLDashboard', management: 'managed', dependsOn: ['telemetry_db'] },
    { key: 'analytics_lakehouse', type: 'Lakehouse', displayName: 'FoilAnalytics', definitionPath: 'fabric/FoilAnalytics.Lakehouse', management: 'managed', dependsOn: [] },
    { key: 'notebook_environment', type: 'Environment', displayName: 'FoilPython', definitionPath: 'fabric/FoilPython.Environment', management: 'managed', dependsOn: [] },
    { key: 'quality_notebook', type: 'Notebook', displayName: 'FoilQuality', definitionPath: 'fabric/FoilQuality.Notebook', management: 'managed', dependsOn: ['analytics_lakehouse', 'notebook_environment'] },
  ],
  dataFlows: [
    { from: 'telemetry_stream', to: 'telemetry_db', kind: 'events', evidence: 'declared' },
    { from: 'telemetry_db', to: 'realtime_dashboard', kind: 'query', evidence: 'declared' },
    { from: 'analytics_lakehouse', to: 'quality_notebook', kind: 'batch', evidence: 'declared' },
  ],
  telemetry: {
    sourceConnectionRef: 'secretref:foil/event-source',
    eventIdField: 'event_id',
    eventTimeField: 'event_time',
    freshnessTargetSeconds: 60,
  },
};
