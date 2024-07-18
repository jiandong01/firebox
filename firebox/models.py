from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List


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


class ProcessConfig(BaseModel):
    cmd: str = Field(..., description="Command to execute")
    env_vars: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables for the process"
    )
    cwd: Optional[str] = Field(
        default=None, description="Working directory for the process"
    )
    timeout: int = Field(default=60, description="Timeout for the process in seconds")


class FileSystemOperation(BaseModel):
    operation: str = Field(..., description="Type of filesystem operation")
    path: str = Field(..., description="Path for the filesystem operation")
    content: Optional[str] = Field(
        default=None, description="Content for write operations"
    )
    timeout: int = Field(
        default=30, description="Timeout for the filesystem operation in seconds"
    )


class RunningProcess(BaseModel):
    pid: int = Field(..., description="Process ID")
    cmd: str = Field(..., description="Command that was executed")
    status: str = Field(..., description="Current status of the process")
    exit_code: Optional[int] = Field(
        default=None, description="Exit code of the process if completed"
    )


class SandboxStatus(BaseModel):
    sandbox_id: str = Field(..., description="Unique identifier of the sandbox")
    status: str = Field(..., description="Current status of the sandbox")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Metadata associated with the sandbox"
    )
