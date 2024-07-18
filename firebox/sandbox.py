import docker
from docker import DockerClient
import asyncio
import uuid
from typing import Optional, Any, Dict, List
from docker.errors import APIError
from .process import Process
from .filesystem import Filesystem
from .models import SandboxConfig
from .exceptions import SandboxError, TimeoutError
from .config import config
from .logs import logger


class Sandbox:
    def __init__(self, sandbox_config: Optional[SandboxConfig] = None):
        self.config = sandbox_config or SandboxConfig()
        self.id = self.config.sandbox_id or str(uuid.uuid4())
        self.client = docker.from_env()
        self.container = None
        self.process = Process(self)
        self.filesystem = Filesystem(self)
        self.cwd = self.config.cwd
        self.metadata = self.config.metadata or {}

    async def init(self):
        logger.info(f"Initializing sandbox with ID: {self.id}")
        if self.config.dockerfile:
            await self._build_image()

        try:
            self.container = self.client.containers.get(
                f"{config.container_prefix}_{self.id}"
            )
            logger.info(
                f"Container {config.container_prefix}_{self.id} already exists, status: {self.container.status}"
            )
        except docker.errors.NotFound:
            logger.info(f"Creating new container {config.container_prefix}_{self.id}")
            try:
                self.container = self.client.containers.run(
                    self.config.image,
                    name=f"{config.container_prefix}_{self.id}",
                    detach=True,
                    tty=True,
                    stdin_open=True,
                    cpu_count=self.config.cpu,
                    mem_limit=self.config.memory,
                    volumes=self.config.volumes,
                    environment=self.config.environment,
                    working_dir=self.cwd,
                    command="tail -f /dev/null",  # Keep container running
                )
            except docker.errors.APIError as e:
                logger.error(f"Failed to create container: {str(e)}")
                raise APIError(f"Failed to create container: {str(e)}")

        if self.container.status != "running":
            logger.info(f"Starting container {config.container_prefix}_{self.id}")
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

        logger.info(f"Container {config.container_prefix}_{self.id} is running")
        await self.ensure_container_ready()
        await self._init_scripts()

    async def _build_image(self):
        logger.info(f"Building image from Dockerfile: {self.config.dockerfile}")
        try:
            self.client.images.build(
                path=".",
                dockerfile=self.config.dockerfile,
                tag=self.config.image,
            )
        except docker.errors.BuildError as e:
            logger.error(f"Failed to build image: {str(e)}")
            raise SandboxError(f"Failed to build image: {str(e)}")

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
            workdir=self.cwd,
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
                f"Stopping and removing container {config.container_prefix}_{self.id} and its associated volume"
            )
            try:
                self.container.remove(v=True, force=True)
                logger.info(
                    f"Container {config.container_prefix}_{self.id} and its associated volume removed successfully"
                )
            except docker.errors.NotFound:
                logger.warning(
                    f"Container {config.container_prefix}_{self.id} not found, it may have been already removed"
                )
            except docker.errors.APIError as e:
                logger.error(
                    f"Failed to remove container {config.container_prefix}_{self.id} and its volume: {str(e)}"
                )
                raise SandboxError(f"Failed to remove container and volume: {str(e)}")
            finally:
                self.container = None
        else:
            logger.warning(f"No container to remove for sandbox {self.id}")

        logger.info(f"Sandbox {self.id} closed successfully")

    @classmethod
    async def reconnect(cls, sandbox_id: str) -> "Sandbox":
        logger.info(f"Reconnecting to sandbox with ID: {sandbox_id}")
        sandbox_config = SandboxConfig(sandbox_id=sandbox_id)
        sandbox = cls(sandbox_config)
        await sandbox.init()
        return sandbox

    def get_hostname(self, port: Optional[int] = None) -> str:
        base_url = f"{self.id}.sandbox.{config.domain}"
        return f"{base_url}:{port}" if port else base_url

    def set_metadata(self, key: str, value: Any):
        self.metadata[key] = value

    def get_metadata(self, key: str) -> Any:
        return self.metadata.get(key)

    def set_cwd(self, path: str):
        self.cwd = path
        if self.container:
            self.container.exec_run(f"cd {path}")

    async def keep_alive(self, duration: int):
        """Keep the sandbox alive for the specified duration (in milliseconds)."""
        logger.info(f"Keeping sandbox {self.id} alive for {duration}ms")
        await asyncio.sleep(duration / 1000)

    @classmethod
    async def list(cls) -> List[Dict[str, Any]]:
        """List all running sandboxes."""
        client = docker.from_env()
        containers = client.containers.list(
            filters={"name": f"{config.container_prefix}_"}
        )
        return [
            {
                "sandbox_id": container.name.split("_")[-1],
                "status": container.status,
                "metadata": container.labels.get("metadata", {}),
            }
            for container in containers
        ]
