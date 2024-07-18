import docker
import asyncio
from typing import Optional, Any
from docker.errors import APIError
from .process import Process
from .filesystem import Filesystem
from .config import SandboxConfig
from .exceptions import SandboxError, TimeoutError
from .logs import setup_logging

logger = setup_logging()


class Sandbox:
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or config.fireenv.sandbox
        self.id = config.sandbox_id
        self.image_name = config.image_name
        self.client = docker.from_env()
        self.container = None
        self.cpu = config.cpu
        self.memory = config.memory
        self.volume_name = f"{self.id}_volume"
        self.env_vars = {**config.environment}
        self.volumes = config.volumes
        self.process = Process(self)
        self.filesystem = Filesystem(self)
        self.last_output = "Environment initialized"
        self.metadata = config.metadata

    async def init(self):
        logger.info(f"Initializing sandbox with ID: {self.id}")
        try:
            self.container = self.client.containers.get(f"sandbox_{self.id}")
            logger.info(
                f"Container sandbox_{self.id} already exists, status: {self.container.status}"
            )
        except docker.errors.NotFound:
            logger.info(f"Creating new container sandbox_{self.id}")
            try:
                self.container = self.client.containers.run(
                    self.image_name,
                    name=f"sandbox_{self.id}",
                    detach=True,
                    tty=True,
                    stdin_open=True,
                    cpu_count=self.cpu,
                    mem_limit=self.memory,
                    volumes=self.volumes,
                    environment=self.env_vars,
                    command="tail -f /dev/null",  # Keep container running
                )
            except docker.errors.APIError as e:
                logger.error(f"Failed to create container: {str(e)}")
                raise APIError(f"Failed to create container: {str(e)}")

        if self.container.status != "running":
            logger.info(f"Starting container sandbox_{self.id}")
            try:
                self.container.start()
            except docker.errors.APIError as e:
                logger.error(f"Failed to start container: {str(e)}")
                raise APIError(f"Failed to start container: {str(e)}")

        self.container.reload()
        if self.container.status != "running":
            logs = self.container.logs().decode("utf-8")
            logger.error(f"Container failed to start. Logs:\n{logs}")
            raise RuntimeError(
                f"Failed to start container. Status: {self.container.status}"
            )

        logger.info(f"Container sandbox_{self.id} is running")
        await self.ensure_container_ready()
        await self._init_scripts()

    async def _init_scripts(self):
        logger.info("Initializing scripts")
        commands = [
            "source /root/.bashrc",
            "mkdir -p /root/commands",
            "touch /root/commands/__init__.py",
            "export PATH=$PATH:/root/commands",
        ]
        for cmd in commands:
            await self.communicate(cmd)

    async def add_script(self, name: str, content: str) -> None:
        """Add a custom script to the sandbox."""
        logger.info("Add custom scripts")
        script_path = f"/root/commands/{name}"
        escaped_content = content.replace('"', '\\"')
        command = f'echo "{escaped_content}" > {script_path} && chmod +x {script_path}'
        await self.communicate(command)

    async def communicate(self, command: str, timeout: int = 60) -> tuple[str, int]:
        logger.info(f"Executing command: {command}")
        try:
            exec_result = await asyncio.wait_for(
                self._exec_run(command), timeout=timeout
            )
            output = exec_result.output.decode("utf-8").strip()
            exit_code = exec_result.exit_code
            logger.info(f"Raw command output: '{output}', exit code: {exit_code}")
            # TODO: better state management
            logger.info(f"communicate last output: '{output}' ")
            self.last_output = output
            return output, exit_code
        except asyncio.TimeoutError:
            logger.error(f"Command execution timed out after {timeout} seconds")
            raise TimeoutError(f"Command execution timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Command execution failed: {str(e)}")
            raise SandboxError(f"Command execution failed: {str(e)}")

    async def _exec_run(self, command: str):
        return await asyncio.to_thread(
            self.container.exec_run,
            cmd=["/bin/bash", "-c", command],
            stream=False,
            demux=False,
        )

    async def ensure_container_ready(self):
        max_retries = 5
        retry_delay = 1
        for _ in range(max_retries):
            self.container.reload()
            if self.container.status == "running":
                return
            await asyncio.sleep(retry_delay)
        raise RuntimeError(f"Container failed to start after {max_retries} retries")

    async def close(self):
        if self.container:
            logger.info(
                f"Stopping and removing container sandbox_{self.id} and its associated volume"
            )
            try:
                self.container.remove(v=True, force=True)
                logger.info(
                    f"Container sandbox_{self.id} and its associated volume removed successfully"
                )
            except docker.errors.NotFound:
                logger.warning(
                    f"Container sandbox_{self.id} not found, it may have been already removed"
                )
            except docker.errors.APIError as e:
                logger.error(
                    f"Failed to remove container sandbox_{self.id} and its volume: {str(e)}"
                )
                raise SandboxError(f"Failed to remove container and volume: {str(e)}")
            finally:
                self.container = None
        else:
            logger.warning(f"No container to remove for sandbox_{self.id}")

        logger.info(f"Sandbox {self.id} closed successfully")

    @classmethod
    async def reconnect(cls, sandbox_id: str) -> "Sandbox":
        logger.info(f"Reconnecting to sandbox with ID: {sandbox_id}")
        config = SandboxConfig(sandbox_id=sandbox_id)
        sandbox = cls(config)
        await sandbox.init()
        return sandbox

    def get_hostname(self, port: Optional[int] = None) -> str:
        base_url = f"{self.id}.sandbox.yourdomain.com"
        return f"{base_url}:{port}" if port else base_url

    def set_metadata(self, key: str, value: Any):
        self.metadata[key] = value

    def get_metadata(self, key: str) -> Any:
        return self.metadata.get(key)
