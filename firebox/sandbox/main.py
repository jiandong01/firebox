import docker
import asyncio
from typing import Any, Callable, Dict, List, Optional, Union

from .docker_sandbox import DockerSandbox
from firebox.filesystem import FilesystemManager
from firebox.process import ProcessManager, Process, ProcessMessage, ProcessOutput
from firebox.terminal import TerminalManager
from firebox.code_snippet import CodeSnippetManager, OpenPort
from firebox.models import DockerSandboxConfig, EnvVars, SandboxStatus, SandboxInfo
from firebox.exception import SandboxException
from firebox.constants import TIMEOUT, DOMAIN
from firebox.logs import logger


class Sandbox:
    """
    Firebox sandbox provides a secure, isolated environment for running code and commands.
    It's based on Docker and offers similar functionality to e2b's cloud sandbox.
    """

    _closed_sandboxes: Dict[str, "Sandbox"] = {}

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
    def container(self):
        return self._docker_sandbox.container

    @property
    def is_open(self) -> bool:
        return self._status == SandboxStatus.RUNNING

    @property
    def cwd(self):
        return self._cwd

    @cwd.setter
    def cwd(self, new_cwd):
        self._cwd = new_cwd
        if hasattr(self, "_docker_sandbox"):
            self._docker_sandbox.cwd = new_cwd

    @property
    def status(self) -> SandboxStatus:
        return self._status

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
        self._cwd = cwd or "/sandbox"
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
                cwd=self._cwd,
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
        self._status = SandboxStatus.CREATED

    async def open(self, timeout: Optional[float] = TIMEOUT) -> None:
        logger.info(
            f"Opening sandbox with template {self._docker_sandbox.config.image}"
        )
        try:
            await self._docker_sandbox.init(timeout=timeout)
            asyncio.create_task(self._code_snippet.subscribe())
            logger.info(f"Sandbox opened successfully")

            if self._cwd:
                await self._filesystem.make_dir(self._cwd)

            self._status = SandboxStatus.RUNNING
        except Exception as e:
            logger.error(f"Failed to open sandbox: {str(e)}")
            await self.close()
            raise SandboxException(f"Failed to open sandbox: {str(e)}") from e

    async def close(self) -> None:
        if self._status == SandboxStatus.RELEASED:
            raise SandboxException("Cannot close a released sandbox")

        logger.info(f"Closing sandbox {self.id}")
        await self._docker_sandbox.stop()
        self._status = SandboxStatus.CLOSED
        Sandbox._closed_sandboxes[self.id] = self
        logger.info(f"Sandbox {self.id} closed")

    async def release(self) -> None:
        logger.info(f"Releasing sandbox {self.id}")
        await self._docker_sandbox.remove()
        self._status = SandboxStatus.RELEASED
        if self.id in Sandbox._closed_sandboxes:
            del Sandbox._closed_sandboxes[self.id]
        logger.info(f"Sandbox {self.id} released")

    @classmethod
    async def create(cls, *args, **kwargs):
        sandbox = cls(*args, **kwargs)
        await sandbox.open()
        return sandbox

    async def keep_alive(self, duration: int) -> None:
        if not 0 <= duration <= 3600:
            raise ValueError("Duration must be between 0 and 3600 seconds")

        logger.info(f"Keeping sandbox {self.id} alive for {duration} seconds")
        await self._docker_sandbox.keep_alive(duration)

    @classmethod
    async def reconnect(cls, sandbox_id: str, **kwargs):
        logger.info(f"Reconnecting to sandbox {sandbox_id}")
        if sandbox_id in cls._closed_sandboxes:
            sandbox = cls._closed_sandboxes[sandbox_id]
            await sandbox._docker_sandbox.start()
            sandbox._status = SandboxStatus.RUNNING
            del cls._closed_sandboxes[sandbox_id]
            return sandbox

        try:
            docker_sandbox = DockerSandbox.get(sandbox_id)
            sandbox = cls(_sandbox=docker_sandbox, **kwargs)
            await sandbox._docker_sandbox.start()
            sandbox._status = SandboxStatus.RUNNING
            return sandbox
        except docker.errors.NotFound:
            raise SandboxException(f"Sandbox with ID {sandbox_id} not found")

    @staticmethod
    def list(include_closed=False) -> List[SandboxInfo]:
        docker_client = docker.from_env()
        sandboxes = []
        for container in docker_client.containers.list(
            all=True, filters={"name": "firebox-sandbox_"}
        ):
            sandbox_id = container.name.split("_")[1]
            sandboxes.append(
                SandboxInfo(
                    sandbox_id=sandbox_id,
                    status=(
                        SandboxStatus.RUNNING
                        if container.status == "running"
                        else SandboxStatus.CLOSED
                    ),
                    metadata={
                        "name": container.name,
                        "image": (
                            container.image.tags[0]
                            if container.image.tags
                            else "unknown"
                        ),
                        "created": container.attrs["Created"],
                    },
                )
            )
        if include_closed:
            sandboxes.extend(
                [
                    SandboxInfo(
                        sandbox_id=s.id,
                        status=s.status,
                        metadata={
                            "name": s._docker_sandbox.container.name,
                            "image": s._docker_sandbox.config.image,
                            "created": s._docker_sandbox.container.attrs["Created"],
                        },
                    )
                    for s in Sandbox._closed_sandboxes.values()
                ]
            )
        return sandboxes

    @staticmethod
    def kill(sandbox_id: str, domain: str = DOMAIN) -> None:
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
        asyncio.get_event_loop().run_until_complete(self.close())
