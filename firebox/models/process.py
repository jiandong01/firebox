from pydantic import BaseModel, Field
from typing import Dict, Optional


class ProcessConfig(BaseModel):
    cmd: str = Field(..., description="Command to execute")
    env_vars: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables for the process"
    )
    cwd: Optional[str] = Field(
        default=None, description="Working directory for the process"
    )
    timeout: int = Field(default=60, description="Timeout for the process in seconds")


class RunningProcess(BaseModel):
    pid: int = Field(..., description="Process ID")
    cmd: str = Field(..., description="Command that was executed")
    status: str = Field(..., description="Current status of the process")
    exit_code: Optional[int] = Field(
        default=None, description="Exit code of the process if completed"
    )
