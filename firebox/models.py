from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class SandboxConfig(BaseModel):
    image: str = Field(default="fireenv-sandbox:latest")
    dockerfile: Optional[str] = None
    cpu: int = Field(default=1)
    memory: str = Field(default="1g")
    environment: Dict[str, str] = Field(default_factory=dict)
    volumes: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    cwd: str = Field(default="/home/user")


class ProcessConfig(BaseModel):
    cmd: str
    env_vars: Dict[str, str] = Field(default_factory=dict)
    cwd: Optional[str] = None
    timeout: int = Field(default=30)


class FileSystemOperation(BaseModel):
    operation: str
    path: str
    content: Optional[str] = None
    timeout: int = Field(default=30)
