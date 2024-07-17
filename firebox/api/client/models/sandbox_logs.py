from pydantic import BaseModel, Field
from typing import List
from datetime import datetime


class SandboxLog(BaseModel):
    timestamp: datetime = Field(..., description="Timestamp of the log entry")
    line: str = Field(..., description="Log line content")


class SandboxLogs(BaseModel):
    logs: List[SandboxLog] = Field(..., description="List of log entries")
