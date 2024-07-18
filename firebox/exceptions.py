from docker.errors import BuildError


class SandboxError(Exception):
    """Base exception for sandbox-related errors."""


class SandboxBuildError(BuildError):
    """Base exception for sandbox-related build errors."""


class FilesystemError(SandboxError):
    """Exception raised for filesystem-related errors."""


class FileNotFoundError(FilesystemError):
    """Exception raised for filesystem-related file not found errors."""


class OSError(FilesystemError):
    """Exception raised for filesystem-related OS errors."""


class IOError(FilesystemError):
    """Exception raised for filesystem-related IO errors."""


class ProcessError(SandboxError):
    """Exception raised for process-related errors."""


class CommunicationError(SandboxError):
    """Exception raised for errors in communicating with the sandbox."""


class TimeoutError(SandboxError):
    """Exception raised when an operation times out."""
