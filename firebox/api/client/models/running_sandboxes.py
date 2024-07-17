from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime


class RunningSandboxes(BaseModel):
    template_id: str = Field(
        ..., alias="templateID", description="Identifier of the template"
    )
    sandbox_id: str = Field(
        ..., alias="sandboxID", description="Identifier of the sandbox"
    )
    client_id: str = Field(
        ..., alias="clientID", description="Identifier of the client"
    )
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
    alias: Optional[str] = Field(None, description="Alias of the template")
