import docker
import asyncio
from typing import Any, Callable, Dict, List, Optional, Union

from .docker_sandbox import DockerSandbox
from firebox.filesystem import FilesystemManager
from firebox.process import ProcessManager, Process, ProcessMessage, ProcessOutput
from firebox.terminal import TerminalManager
from firebox.code_snippet import CodeSnippetManager, OpenPort
from firebox.models import DockerSandboxConfig, EnvVars
from firebox.exception import (
    SandboxException,
)
from firebox.constants import TIMEOUT, DOMAIN
from firebox.logs import logger


class Sandbox:
    """
    Firebox sandbox provides a secure, isolated environment for running code and commands.
    It's based on Docker and offers similar functionality to e2b's cloud sandbox.
    """

    @property
    def process(self) -> ProcessManager:
        """
        Process manager used to run commands.
        """
        return self._process

    @property
    def terminal(self) -> TerminalManager:
        """
        Terminal manager used to create interactive terminals.
        """
        return self._terminal

    @property
    def filesystem(self) -> FilesystemManager:
        """
        Filesystem manager used to manage files.
        """
        return self._filesystem

    @property
    def id(self) -> str:
        """
        The sandbox ID.
        """
        return self._docker_sandbox.id

    @property
    def is_open(self) -> bool:
        """
        Whether the sandbox is open.
        """
        return self._docker_sandbox.is_running()

    def __init__(
        self,
        template: Union[str, DockerSandboxConfig] = "base",
        cwd: Optional[str] = None,
        env_vars: Optional[EnvVars] = None,
        on_scan_ports: Optional[Callable[[List[OpenPort]], Any]] = None,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Union[Callable[[int], Any], Callable[[], Any]]] = None,
        metadata: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = TIMEOUT,
        domain: str = DOMAIN,
    ):
        """
        Create a new sandbox.

        :param template: Name of the Docker image to use as a template.
        :param cwd: The current working directory to use.
        :param env_vars: A dictionary of environment variables to be used for all processes.
        :param on_scan_ports: A callback to handle opened ports.
        :param on_stdout: A default callback that is called when stdout with a newline is received from the process.
        :param on_stderr: A default callback that is called when stderr with a newline is received from the process.
        :param on_exit: A default callback that is called when the process exits.
        :param metadata: A dictionary of strings that is stored alongside the running sandbox.
        :param timeout: Timeout for sandbox to initialize in seconds, default is 60 seconds.
        :param domain: The domain to use for the API.
        """
        self.cwd = cwd or "/sandbox"
        self.env_vars = env_vars or {}
        self.domain = domain

        if isinstance(template, DockerSandboxConfig):
            self._docker_sandbox_config = template
        else:
            self._docker_sandbox_config = DockerSandboxConfig(
                image=template,
                cpu=1,
                memory="1g",
                environment=self.env_vars,
                cwd=self.cwd,
                metadata=metadata,
            )

        self._docker_sandbox = DockerSandbox(self._docker_sandbox_config)
        self._code_snippet = CodeSnippetManager(
            sandbox=self._docker_sandbox,
            on_scan_ports=on_scan_ports,
        )
        self._terminal = TerminalManager(sandbox=self._docker_sandbox)
        self._filesystem = FilesystemManager(sandbox=self._docker_sandbox)
        self._process = ProcessManager(
            sandbox=self._docker_sandbox,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            on_exit=on_exit,
        )

    async def open(self, timeout: Optional[float] = TIMEOUT) -> None:
        """
        Open the sandbox.

        :param timeout: Specify the duration, in seconds to give the method to finish its execution before it times out.
        """
        logger.info(
            f"Opening sandbox with template {self._docker_sandbox.config.image}"
        )
        try:
            await self._docker_sandbox.init(timeout=timeout)
            asyncio.create_task(self._code_snippet.subscribe())
            logger.info(f"Sandbox opened successfully")

            if self.cwd:
                await self._filesystem.make_dir(self.cwd)
        except Exception as e:
            logger.error(f"Failed to open sandbox: {str(e)}")
            await self.close()
            raise SandboxException(f"Failed to open sandbox: {str(e)}") from e

    async def close(self) -> None:
        """
        Close the sandbox and clean up resources.
        """
        logger.info(f"Closing sandbox {self.id}")
        await self._docker_sandbox.close()
        logger.info(f"Sandbox {self.id} closed")

    @classmethod
    async def create(cls, *args, **kwargs):
        sandbox = cls(*args, **kwargs)
        await sandbox.open()
        return sandbox

    def keep_alive(self, duration: int) -> None:
        """
        Keep the sandbox alive for the specified duration.

        :param duration: Duration in seconds. Must be between 0 and 3600 seconds.
        """
        if not 0 <= duration <= 3600:
            raise ValueError("Duration must be between 0 and 3600 seconds")

        logger.info(f"Keeping sandbox {self.id} alive for {duration} seconds")
        self._docker_sandbox.keep_alive(duration)

    @classmethod
    def reconnect(cls, sandbox_id: str, **kwargs):
        """
        Reconnects to a previously created sandbox.

        :param sandbox_id: ID of the sandbox to reconnect to
        :param kwargs: Additional arguments to pass to the Sandbox constructor
        """
        logger.info(f"Reconnecting to sandbox {sandbox_id}")
        docker_client = docker.from_env()
        try:
            container = docker_client.containers.get(sandbox_id)
            if container.status != "running":
                container.start()

            config = DockerSandboxConfig(
                sandbox_id=sandbox_id,
                image=container.image.tags[0] if container.image.tags else "unknown",
                **kwargs,
            )
            return cls(_sandbox=DockerSandbox(config), **kwargs)
        except docker.errors.NotFound:
            raise SandboxException(f"Sandbox with ID {sandbox_id} not found")

    @staticmethod
    def list(domain: str = DOMAIN) -> List[Dict[str, Any]]:
        """
        List all running sandboxes.

        :param domain: The domain to use for the API.
        :return: List of dictionaries containing information about running sandboxes.
        """
        docker_client = docker.from_env()
        sandboxes = []
        for container in docker_client.containers.list(
            filters={"label": "firebox.sandbox"}
        ):
            sandboxes.append(
                {
                    "id": container.id,
                    "name": container.name,
                    "status": container.status,
                    "image": (
                        container.image.tags[0] if container.image.tags else "unknown"
                    ),
                    "created": container.attrs["Created"],
                }
            )
        return sandboxes

    @staticmethod
    def kill(sandbox_id: str, domain: str = DOMAIN) -> None:
        """
        Kill the running sandbox specified by the sandbox ID.

        :param sandbox_id: ID of the sandbox to kill.
        :param domain: The domain to use for the API.
        """
        docker_client = docker.from_env()
        try:
            container = docker_client.containers.get(sandbox_id)
            container.remove(force=True)
            logger.info(f"Sandbox {sandbox_id} killed and removed")
        except docker.errors.NotFound:
            raise SandboxException(f"Sandbox with ID {sandbox_id} not found")

    async def start_process(
        self,
        cmd: str,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Union[Callable[[int], Any], Callable[[], Any]]] = None,
        env_vars: Optional[EnvVars] = None,
        cwd: Optional[str] = None,
        timeout: Optional[float] = TIMEOUT,
    ) -> Process:
        """
        Start a new process in the sandbox.

        :param cmd: The command to run.
        :param on_stdout: Callback for stdout messages.
        :param on_stderr: Callback for stderr messages.
        :param on_exit: Callback for when the process exits.
        :param env_vars: Additional environment variables for the process.
        :param cwd: Working directory for the process.
        :param timeout: Timeout for starting the process.
        :return: A Process object representing the started process.
        """
        return await self._process.start(
            cmd,
            on_stdout,
            on_stderr,
            on_exit,
            env_vars,
            cwd or self.cwd,
            timeout=timeout,
        )

    async def start_and_wait(
        self,
        cmd: str,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Callable[[int], Any]] = None,
        env_vars: Optional[EnvVars] = None,
        cwd: Optional[str] = None,
        timeout: Optional[float] = TIMEOUT,
    ) -> ProcessOutput:
        """
        Start a new process in the sandbox and wait for it to complete.

        :param cmd: The command to run.
        :param on_stdout: Callback for stdout messages.
        :param on_stderr: Callback for stderr messages.
        :param on_exit: Callback for when the process exits.
        :param env_vars: Additional environment variables for the process.
        :param cwd: Working directory for the process.
        :param timeout: Timeout for the entire operation.
        :return: A ProcessOutput object containing the results of the process.
        """
        return await self._process.start_and_wait(
            cmd,
            on_stdout,
            on_stderr,
            on_exit,
            env_vars,
            cwd or self.cwd,
            timeout=timeout,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
