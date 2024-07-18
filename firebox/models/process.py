from pydantic import BaseModel, Field
from typing import Dict, Optional, ClassVar, List

EnvVars = Dict[str, str]


class ProcessMessage(BaseModel):
    """
    A message from a process.
    """

    line: str
    error: bool = False
    timestamp: int
    """
    Unix epoch in nanoseconds
    """

    def __str__(self):
        return self.line


class ProcessOutput(BaseModel):
    """
    Output from a process.
    """

    delimiter: ClassVar[str] = "\n"
    messages: List[ProcessMessage] = []

    error: bool = False
    exit_code: Optional[int] = None

    @property
    def stdout(self) -> str:
        """
        The stdout from the process.
        """
        return self.delimiter.join(out.line for out in self.messages if not out.error)

    @property
    def stderr(self) -> str:
        """
        The stderr from the process.
        """
        return self.delimiter.join(out.line for out in self.messages if out.error)

    def _insert_by_timestamp(self, message: ProcessMessage):
        """Insert an out based on its timestamp using insertion sort."""
        i = len(self.messages) - 1
        while i >= 0 and self.messages[i].timestamp > message.timestamp:
            i -= 1
        self.messages.insert(i + 1, message)

    def _add_stdout(self, message: ProcessMessage):
        self._insert_by_timestamp(message)

    def _add_stderr(self, message: ProcessMessage):
        self.error = True
        self._insert_by_timestamp(message)


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
