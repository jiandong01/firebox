from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime


class Error(BaseModel):
    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")


from typing import Dict, Optional, List
from pydantic import BaseModel, Field


class NewSandbox(BaseModel):
    template_id: str = Field(
        ..., alias="templateID", description="Identifier of the required template"
    )
    metadata: Optional[Dict[str, str]] = Field(
        None, description="Additional metadata for the sandbox"
    )
    cpu_count: Optional[int] = Field(None, description="Number of CPUs to allocate")
    memory_mb: Optional[int] = Field(None, description="Memory limit in MB")
    volumes: Optional[Dict[str, str]] = Field(
        None, description="Volume mounts: {host_path: container_path}"
    )
    ports: Optional[Dict[str, int]] = Field(
        None, description="Port mappings: {container_port: host_port}"
    )
    capabilities: Optional[List[str]] = Field(
        None, description="Linux capabilities to add"
    )
    dockerfile: Optional[str] = Field(
        None, description="Dockerfile content for custom images"
    )
    build_args: Optional[Dict[str, str]] = Field(
        None, description="Build arguments for custom images"
    )


class Sandbox(BaseModel):
    template_id: str = Field(
        ..., alias="templateID", description="Identifier of the template"
    )
    sandbox_id: str = Field(
        ..., alias="sandboxID", description="Identifier of the sandbox"
    )
    client_id: str = Field(
        ..., alias="clientID", description="Identifier of the client"
    )
    alias: Optional[str] = Field(None, description="Alias of the template")


class RunningSandboxes(Sandbox):
    started_at: datetime = Field(
        ..., alias="startedAt", description="Time when the sandbox was started"
    )
    cpu_count: int = Field(
        ..., alias="cpuCount", description="CPU cores for the sandbox"
    )
    memory_mb: int = Field(
        ..., alias="memoryMB", description="Memory limit for the sandbox in MB"
    )
    metadata: Optional[Dict[str, str]] = Field(
        None, description="Additional metadata for the sandbox"
    )


class SandboxLog(BaseModel):
    timestamp: datetime = Field(..., description="Timestamp of the log entry")
    line: str = Field(..., description="Log line content")


class SandboxLogs(BaseModel):
    logs: List[SandboxLog] = Field(..., description="List of log entries")
