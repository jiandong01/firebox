import asyncio
import threading
from typing import Optional, Any, Dict, List, Callable, Union, IO
from .docker_sandbox import DockerSandbox
from .process import ProcessManager
from .filesystem import FilesystemManager
from .models import SandboxConfig, EnvVars, ProcessMessage, OpenPort
from .config import config
from .logs import logger


class Sandbox:
    def __init__(
        self,
        template: str = "base",
        sandbox_config: Optional[SandboxConfig] = None,
        api_key: Optional[str] = None,
        cwd: Optional[str] = None,
        env_vars: Optional[EnvVars] = None,
        on_scan_ports: Optional[Callable[[List[OpenPort]], Any]] = None,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Union[Callable[[int], Any], Callable[[], Any]]] = None,
        metadata: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = config.timeout,
        **kwargs,
    ):
        self.config = sandbox_config or SandboxConfig(template=template)
        self.api_key = api_key
        self.cwd = cwd or self.config.cwd
        self.env_vars = env_vars or {}
        self.on_scan_ports = on_scan_ports
        self.on_stdout = on_stdout
        self.on_stderr = on_stderr
        self.on_exit = on_exit
        self.metadata = metadata or {}
        self.timeout = timeout

        self._docker_sandbox = DockerSandbox(
            self.config,
            env_vars=self.env_vars,
            on_stdout=self.on_stdout,
            on_stderr=self.on_stderr,
            on_exit=self.on_exit,
        )
        self._process_manager = ProcessManager(self._docker_sandbox)
        self._filesystem_manager = FilesystemManager(self._docker_sandbox)
        self._process_cleanup = []

    @property
    def id(self) -> str:
        return self._docker_sandbox.id

    @property
    def process(self) -> ProcessManager:
        return self._process_manager

    @property
    def filesystem(self) -> FilesystemManager:
        return self._filesystem_manager

    async def init(self):
        await self._docker_sandbox.init(timeout=self.timeout)
        await self._init_scripts()
        if self.on_scan_ports:
            open_ports = await self._docker_sandbox.scan_ports()
            self.on_scan_ports(open_ports)

        if self.on_stderr or self.on_stdout:
            self._handle_start_cmd_logs()

    async def _init_scripts(self):
        logger.info("Initializing scripts")
        commands = [
            "source /root/.bashrc",
            "mkdir -p /root/commands",
            "touch /root/commands/__init__.py",
            "export PATH=$PATH:/root/commands",
        ]
        for cmd in commands:
            await self._docker_sandbox.communicate(cmd)

    def _handle_start_cmd_logs(self):
        def run_in_thread():
            asyncio.run(
                self.process.start(
                    "sudo journalctl --follow --lines=all -o cat _SYSTEMD_UNIT=start_cmd.service",
                    cwd="/",
                    env_vars={},
                )
            )

        thread = threading.Thread(target=run_in_thread)
        thread.start()
        self._process_cleanup.append(thread.join)

    async def add_script(self, name: str, content: str) -> None:
        """Add a custom script to the sandbox."""
        logger.info("Add custom scripts")
        script_path = f"/root/commands/{name}"
        escaped_content = content.replace('"', '\\"')
        command = f'echo "{escaped_content}" > {script_path} && chmod +x {script_path}'
        await self._docker_sandbox.communicate(command)

    async def close(self):
        for cleanup in self._process_cleanup:
            cleanup()
        await self._docker_sandbox.close()

    @classmethod
    async def reconnect(
        cls,
        sandbox_id: str,
        cwd: Optional[str] = None,
        env_vars: Optional[EnvVars] = None,
        on_scan_ports: Optional[Callable[[List[OpenPort]], Any]] = None,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Union[Callable[[int], Any], Callable[[], Any]]] = None,
        timeout: Optional[float] = config.timeout,
        api_key: Optional[str] = None,
    ) -> "Sandbox":
        logger.info(f"Reconnecting to sandbox with ID: {sandbox_id}")
        sandbox_config = SandboxConfig(sandbox_id=sandbox_id)
        sandbox = cls(
            sandbox_config=sandbox_config,
            cwd=cwd,
            env_vars=env_vars,
            on_scan_ports=on_scan_ports,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            on_exit=on_exit,
            timeout=timeout,
            api_key=api_key,
        )
        await sandbox.init()
        return sandbox

    def get_hostname(self, port: Optional[int] = None) -> str:
        base_url = f"{self.id}.sandbox.{config.domain}"
        return f"{base_url}:{port}" if port else base_url

    def get_protocol(self, secure: bool = True) -> str:
        return "https" if secure else "http"

    def set_metadata(self, key: str, value: Any):
        self.metadata[key] = value

    def get_metadata(self, key: str) -> Any:
        return self.metadata.get(key)

    def set_cwd(self, path: str):
        self.cwd = path
        self._docker_sandbox.set_cwd(path)

    async def keep_alive(self, duration: int):
        """Keep the sandbox alive for the specified duration (in milliseconds)."""
        logger.info(f"Keeping sandbox {self.id} alive for {duration}ms")
        await asyncio.sleep(duration / 1000)

    @classmethod
    async def list(cls) -> List[Dict[str, Any]]:
        """List all running sandboxes."""
        return await DockerSandbox.list()

    async def __aenter__(self):
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    def file_url(self) -> str:
        """
        Return a URL that can be used to upload files to the sandbox via a multipart/form-data POST request.
        This is useful if you're uploading files directly from the browser.
        The file will be uploaded to the user's home directory with the same name.
        If a file with the same name already exists, it will be overwritten.
        """
        hostname = self.get_hostname(config.ENVD_PORT)
        protocol = self.get_protocol()
        return f"{protocol}://{hostname}{config.FILE_ROUTE}"

    async def upload_file(
        self, file: IO, timeout: Optional[float] = config.timeout
    ) -> str:
        """
        Upload a file to the sandbox.
        The file will be uploaded to the user's home (`/home/user`) directory with the same name.
        If a file with the same name already exists, it will be overwritten.
        """
        return await self._docker_sandbox.upload_file(file, timeout)

    async def download_file(
        self, remote_path: str, timeout: Optional[float] = config.timeout
    ) -> bytes:
        """
        Download a file from the sandbox and returns its content as bytes.
        """
        return await self._docker_sandbox.download_file(remote_path, timeout)
