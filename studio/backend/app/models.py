from typing import Any, Literal
from pydantic import BaseModel, Field


Risk = Literal["read", "write", "admin", "destructive"]


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
    parameters: list[str] = Field(default_factory=list)


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


class SessionStatus(BaseModel):
    mode: Literal["read-only"] = "read-only"
    transport: str = "MicrosoftFabricMgmtMCPServer/core/powershell_session.py"
    feature_provider: str = "MicrosoftFabricMgmt"
