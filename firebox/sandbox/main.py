import logging
import docker
from typing import Any, Callable, Dict, List, Optional, Union

from firebox.docker_sandbox import DockerSandbox
from firebox.filesystem.main import FilesystemManager
from firebox.process.main import ProcessManager, ProcessMessage
from firebox.terminal.main import TerminalManager
from firebox.code_snippet.main import CodeSnippetManager, OpenPort
from firebox.models.sandbox import DockerSandboxConfig, EnvVars
from firebox.exceptions import SandboxException, TimeoutException
from firebox.constants import TIMEOUT

logger = logging.getLogger(__name__)


class Sandbox:
    @property
    def process(self) -> ProcessManager:
        return self._process

    @property
    def terminal(self) -> TerminalManager:
        return self._terminal

    @property
    def filesystem(self) -> FilesystemManager:
        return self._filesystem

    @property
    def id(self) -> str:
        return self._docker_sandbox.id

    @property
    def is_open(self) -> bool:
        return self._docker_sandbox.is_running()

    def __init__(
        self,
        template: str = "base",
        cwd: Optional[str] = None,
        env_vars: Optional[EnvVars] = None,
        on_scan_ports: Optional[Callable[[List[OpenPort]], Any]] = None,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Union[Callable[[int], Any], Callable[[], Any]]] = None,
        metadata: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = TIMEOUT,
    ):
        self.cwd = cwd or "/home/user"
        self.env_vars = env_vars or {}

        config = DockerSandboxConfig(
            image=template,
            cpu=1,
            memory="1g",
            environment=self.env_vars,
            cwd=self.cwd,
            metadata=metadata,
        )

        self._docker_sandbox = DockerSandbox(config)
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

        self._open(timeout=timeout)

    def _open(self, timeout: Optional[float] = TIMEOUT) -> None:
        logger.info(
            f"Opening sandbox with template {self._docker_sandbox.config.image}"
        )
        try:
            self._docker_sandbox.init(timeout=timeout)
            self._code_snippet._subscribe()
            logger.info(f"Sandbox opened successfully")

            if self.cwd:
                self.filesystem.make_dir(self.cwd)
        except Exception as e:
            logger.error(f"Failed to open sandbox: {str(e)}")
            self.close()
            raise SandboxException(f"Failed to open sandbox: {str(e)}") from e

    def close(self) -> None:
        logger.info(f"Closing sandbox {self.id}")
        self._docker_sandbox.close()
        logger.info(f"Sandbox {self.id} closed")

    def keep_alive(self, duration: int) -> None:
        if not 0 <= duration <= 3600:
            raise ValueError("Duration must be between 0 and 3600 seconds")
        logger.info(f"Keeping sandbox {self.id} alive for {duration} seconds")
        self._docker_sandbox.keep_alive(duration)

    @classmethod
    def reconnect(cls, sandbox_id: str, **kwargs):
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
    def list() -> List[Dict[str, Any]]:
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
    def kill(sandbox_id: str) -> None:
        docker_client = docker.from_env()
        try:
            container = docker_client.containers.get(sandbox_id)
            container.remove(force=True)
            logger.info(f"Sandbox {sandbox_id} killed and removed")
        except docker.errors.NotFound:
            raise SandboxException(f"Sandbox with ID {sandbox_id} not found")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
