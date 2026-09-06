from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


Risk = Literal["read", "write", "admin", "destructive"]
ResponseMode = Literal["sync", "fabric-lro"]
ExecutionPolicy = Literal["read", "guarded-write", "blocked"]
MutationStatus = Literal["planned", "validated", "executing", "executed", "failed", "expired"]


class ParameterSpec(BaseModel):
    name: str
    type: str = "string"
    mandatory: bool = False
    is_switch: bool = False
    description: str | None = None
    allowed_values: list[str] = Field(default_factory=list)


class Capability(BaseModel):
    id: str
    title: str
    category: str
    provider: str
    source: str
    risk: Risk = "read"
    command: str | None = None
    endpoint: str | None = None
    description: str = ""
    source_path: str | None = None
    generated: bool = False
    response_mode: ResponseMode = "sync"
    execution_policy: ExecutionPolicy | None = None
    supports_whatif: bool = False
    required_any_of: list[str] = Field(default_factory=list)
    verification_capability_id: str | None = None
    verification_parameter_map: dict[str, str] = Field(default_factory=dict)
    parameters: list[str] = Field(default_factory=list)
    parameter_specs: list[ParameterSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def default_execution_policy(self):
        if self.execution_policy is None:
            self.execution_policy = "read" if self.risk == "read" else "blocked"
        return self


class PreviewRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


class ConnectRequest(BaseModel):
    tenant_id: str = Field(min_length=1)


class ExecutionPreview(BaseModel):
    capability_id: str
    provider: str
    risk: Risk
    command: str | None = None
    endpoint: str | None = None
    rendered_command: str | None = None
    transport: str | None = None
    executable: bool = False
    reason: str = "Execution is disabled for this capability."


class ExecutionResult(BaseModel):
    capability_id: str
    provider: str
    risk: Risk
    rendered_command: str
    result: dict[str, Any]


class MutationPlanRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


class MutationApprovalRequest(BaseModel):
    confirmation: str = Field(min_length=1)


class MutationPlan(BaseModel):
    plan_id: str
    capability_id: str
    capability_title: str
    provider: str
    risk: Risk
    tenant_id: str
    parameters: dict[str, Any]
    rendered_command: str
    validation_command: str | None = None
    supports_validation: bool = False
    confirmation_text: str
    digest: str
    created_at: str
    expires_at: str
    status: MutationStatus = "planned"


class MutationValidationResult(BaseModel):
    plan: MutationPlan
    result: dict[str, Any]


class MutationExecutionResult(BaseModel):
    plan: MutationPlan
    result: dict[str, Any]
    verification: dict[str, Any] | None = None


class SessionStatus(BaseModel):
    mode: Literal["guarded-writes"] = "guarded-writes"
    transport: str = "MicrosoftFabricMgmtMCPServer/core/powershell_session.py"
    feature_provider: str = "MicrosoftFabricMgmt"
    connected: bool = False
    tenant_id: str | None = None
