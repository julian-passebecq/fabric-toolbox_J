from typing import Literal
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


class ExecutionPreview(BaseModel):
    capability_id: str
    provider: str
    risk: Risk
    command: str | None = None
    endpoint: str | None = None
    executable: bool = False
    reason: str = "Execution is disabled in the initial inspect-only backend."
