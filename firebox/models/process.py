from pydantic import BaseModel, Field
from enum import Enum
from typing import Dict, Optional, ClassVar, List
from firebox.utils.str import snake_case_to_camel_case

EnvVars = Dict[str, str]


class ProcessEventType(str, Enum):
    START = "start"
    STOP = "stop"
    EXIT = "exit"
    SIGNAL = "signal"
    STDOUT = "stdout"
    STDERR = "stderr"


class ProcessEvent(BaseModel):
    pid: int
    event_type: ProcessEventType
    timestamp: int  # Unix timestamp in nanoseconds
    exit_code: Optional[int] = None
    signal: Optional[int] = None
    data: Optional[str] = None  # For stdout/stderr events

    class ConfigDict:
        alias_generator = snake_case_to_camel_case  # Assuming you want to use this

    def __str__(self):
        if self.event_type == ProcessEventType.START:
            return f"Process {self.pid} started at {self.timestamp}"
        elif self.event_type == ProcessEventType.STOP:
            return f"Process {self.pid} stopped at {self.timestamp}"
        elif self.event_type == ProcessEventType.EXIT:
            return f"Process {self.pid} exited with code {self.exit_code} at {self.timestamp}"
        elif self.event_type == ProcessEventType.SIGNAL:
            return (
                f"Process {self.pid} received signal {self.signal} at {self.timestamp}"
            )
        elif self.event_type == ProcessEventType.STDOUT:
            return f"Process {self.pid} stdout at {self.timestamp}: {self.data}"
        elif self.event_type == ProcessEventType.STDERR:
            return f"Process {self.pid} stderr at {self.timestamp}: {self.data}"
        else:
            return f"Unknown event for process {self.pid} at {self.timestamp}"


class ProcessMessage(BaseModel):
    line: str
    error: bool = False
    timestamp: int

    def __str__(self):
        return self.line


class ProcessOutput(BaseModel):
    delimiter: ClassVar[str] = "\n"
    messages: List[ProcessMessage] = []
    error: bool = False
    exit_code: Optional[int] = None

    @property
    def stdout(self) -> str:
        return self.delimiter.join(out.line for out in self.messages if not out.error)

    @property
    def stderr(self) -> str:
        return self.delimiter.join(out.line for out in self.messages if out.error)

    def _insert_by_timestamp(self, message: ProcessMessage):
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
