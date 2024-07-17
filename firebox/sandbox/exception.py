from typing import Dict, List, Optional


class SandboxException(Exception):
    """Base exception for all sandbox-related errors."""

    pass


class SandboxNotOpenException(SandboxException):
    """Exception raised when trying to use a sandbox that is not open."""

    pass


class RpcException(SandboxException):
    """Exception raised for RPC-related errors."""

    def __init__(
        self,
        message: str,
        code: int,
        id: str,
        data: Optional[Dict] = None,
    ):
        super().__init__(message)
        self.data = data
        self.code = code
        self.message = message
        self.id = id


class MultipleExceptions(SandboxException):
    """Exception raised when multiple errors occur."""

    def __init__(self, message: str, exceptions: List[Exception]):
        super().__init__(f"Multiple exceptions occurred: {message}")
        self.exceptions = exceptions


class FilesystemException(SandboxException):
    """Exception raised for filesystem-related errors."""

    pass


class ProcessException(SandboxException):
    """Exception raised for process-related errors."""

    pass


class CurrentWorkingDirectoryDoesntExistException(ProcessException):
    """Exception raised when the specified working directory doesn't exist."""

    pass


class TerminalException(SandboxException):
    """Exception raised for terminal-related errors."""

    pass


class AuthenticationException(SandboxException):
    """Exception raised for authentication-related errors."""

    pass


class UnsupportedRuntimeException(SandboxException):
    """Exception raised when an unsupported runtime is requested."""

    pass


class TimeoutException(SandboxException):
    """Exception raised when an operation times out."""

    pass
