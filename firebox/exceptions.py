class FireEnvError(Exception):
    """Base exception for all FireEnv errors."""


class SandboxError(FireEnvError):
    """Base exception for sandbox-related errors."""


class FilesystemError(SandboxError):
    """Exception raised for filesystem-related errors."""


class ProcessError(SandboxError):
    """Exception raised for process-related errors."""


class CommunicationError(SandboxError):
    """Exception raised for errors in communicating with the sandbox."""


class TimeoutError(SandboxError):
    """Exception raised when an operation times out."""


class ConfigurationError(FireEnvError):
    """Exception raised for configuration-related errors."""


class ToolError(FireEnvError):
    """Exception raised for errors related to penetration testing tools."""


class ActionError(FireEnvError):
    """Exception raised for errors during action execution."""


class DependencyError(FireEnvError):
    """Exception raised for errors related to dependencies."""


class PentestError(FireEnvError):
    """Base exception for penetration testing related errors."""


class ReconnaissanceError(PentestError):
    """Exception raised during the reconnaissance phase."""


class VulnerabilityAssessmentError(PentestError):
    """Exception raised during the vulnerability assessment phase."""


class ExploitationError(PentestError):
    """Exception raised during the exploitation phase."""


class PostExploitationError(PentestError):
    """Exception raised during the post-exploitation phase."""


class ReportingError(PentestError):
    """Exception raised during the reporting phase."""


class TrajectoryError(FireEnvError):
    """Exception raised for errors related to trajectory handling."""
