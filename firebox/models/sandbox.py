from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class SandboxConfig(BaseModel):
    sandbox_id: Optional[str] = Field(
        default=None, description="Unique identifier for the sandbox"
    )
    image: str = Field(
        default="fireenv-sandbox:latest",
        description="Docker image name for the sandbox",
    )
    dockerfile: Optional[str] = Field(
        default=None, description="Path to custom Dockerfile"
    )
    dockerfile_context: Optional[str] = Field(
        default=None, description="Path to the Dockerfile context"
    )
    cpu: int = Field(default=1, description="Number of CPUs to allocate to the sandbox")
    memory: str = Field(
        default="1g", description="Amount of memory to allocate to the sandbox"
    )
    environment: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables for the sandbox"
    )
    volumes: Dict[str, Dict[str, str]] = Field(
        default_factory=dict, description="Volume mappings for the sandbox"
    )
    cwd: str = Field(
        default="/home/user", description="Current working directory in the sandbox"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Optional metadata for the sandbox"
    )


class SandboxStatus(BaseModel):
    sandbox_id: str = Field(..., description="Unique identifier of the sandbox")
    status: str = Field(..., description="Current status of the sandbox")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Metadata associated with the sandbox"
    )
