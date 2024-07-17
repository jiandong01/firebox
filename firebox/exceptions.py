class FireboxException(Exception):
    """Base exception for all Firebox-related errors."""


class DockerOperationError(FireboxException):
    """Exception raised when a Docker operation fails."""


class SandboxCreationError(FireboxException):
    """Exception raised when sandbox creation fails."""


class SandboxNotFoundError(FireboxException):
    """Exception raised when a sandbox is not found."""
