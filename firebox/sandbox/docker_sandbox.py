import os
import asyncio
import docker
import uuid
from typing import Optional, Any, Dict, List, Callable
from docker.errors import APIError
from firebox.subscriptions import SubscriptionHandler
from firebox.models import DockerSandboxConfig, OpenPort
from firebox.exception import SandboxException, TimeoutException
from firebox.config import config
from firebox.logs import logger


class DockerSandbox:
    def __init__(self, sandbox_config: DockerSandboxConfig, **kwargs):
        self.config = sandbox_config
        self.id = self.config.sandbox_id or str(uuid.uuid4())
        self.cwd = self.config.cwd
        self.env_vars = self.config.environment
        self.client = docker.from_env()
        self.container = None
        self.kwargs = kwargs

    async def init(self, timeout: Optional[float] = None):
        logger.info(f"Initializing sandbox with ID: {self.id}")

        # Ensure the persistent storage directory exists on the host
        os.makedirs(self.config.persistent_storage_path, exist_ok=True)

        if self.config.dockerfile:
            await self._build_image()

        try:
            self.container = self.client.containers.get(
                f"{config.container_prefix}_{self.id}"
            )
            logger.info(
                f"Container {self.id} already exists, status: {self.container.status}"
            )
        except docker.errors.NotFound:
            logger.info(f"Creating new container {config.container_prefix}_{self.id}")
            try:
                volumes = {
                    os.path.abspath(self.config.persistent_storage_path): {
                        "bind": self.config.cwd,
                        "mode": "rw",
                    }
                }
                container_config = {
                    "image": self.config.image,
                    "name": f"{config.container_prefix}_{self.id}",
                    "detach": True,
                    "tty": True,
                    "stdin_open": True,
                    "cpu_count": self.config.cpu,
                    "mem_limit": self.config.memory,
                    "volumes": volumes,
                    "environment": self.config.environment,
                    "working_dir": self.config.cwd,
                    "command": "tail -f /dev/null",  # Keep container running
                }
                self.container = self.client.containers.run(**container_config)
            except docker.errors.APIError as e:
                logger.error(f"Failed to create container: {str(e)}")
                raise SandboxException(f"Failed to create container: {str(e)}") from e

        if self.container.status != "running":
            logger.info(f"Starting container {self.id}")
            try:
                self.container.start()
            except docker.errors.APIError as e:
                logger.error(f"Failed to start container: {str(e)}")
                raise SandboxException(f"Failed to start container: {str(e)}") from e

        self.container.reload()
        if self.container.status != "running":
            logs = self.container.logs().decode("utf-8")
            logger.error(f"Container failed to start. Logs:\n{logs}")
            raise SandboxException(
                f"Failed to start container. Status: {self.container.status}"
            )

        logger.info(f"Container {config.container_prefix}_{self.id} is running")
        await self._ensure_container_ready(timeout)
        await self._init_scripts()

    async def _build_image(self):
        logger.info(f"Building custom image for sandbox {self.id}")
        try:
            self.client.images.build(
                path=self.config.dockerfile_context,
                dockerfile=self.config.dockerfile,
                tag=self.config.image,
            )
        except docker.errors.BuildError as e:
            logger.error(f"Failed to build custom image: {str(e)}")
            raise SandboxException(f"Failed to build custom image: {str(e)}") from e

    async def _ensure_container_ready(self, timeout: Optional[float] = None):
        start_time = asyncio.get_event_loop().time()
        while True:
            if timeout and asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutException("Container failed to become ready in time")

            try:
                exit_code, output = await self.communicate(
                    "echo 'Container is ready'", timeout=1
                )
                if exit_code == 0 and "Container is ready" in output:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.1)

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

    async def _subscribe(
        self,
        service: str,
        handler: Callable[[Any], None],
        method: str,
        *params,
        timeout: Optional[float] = None,
    ):
        if method == "watchDir":
            return await SubscriptionHandler.watch_directory(self, params[0], handler)
        else:
            raise NotImplementedError(f"Subscription method {method} not implemented")

    async def communicate(
        self, command: str, timeout: Optional[float] = None
    ) -> tuple[int, str]:
        logger.info(f"Executing command: {command}")
        try:
            exec_result = await asyncio.to_thread(
                self.container.exec_run,
                cmd=["/bin/bash", "-c", command],
                workdir=self.config.cwd,
            )
            output = exec_result.output.decode("utf-8").strip()
            exit_code = exec_result.exit_code
            logger.info(f"Command output: '{output}', exit code: {exit_code}")
            return exit_code, output
        except Exception as e:
            logger.error(f"Command execution failed: {str(e)}")
            raise SandboxException(f"Command execution failed: {str(e)}") from e

    async def close(self):
        if self.container:
            logger.info(f"Stopping and removing container {self.id}")
            try:
                self.container.remove(v=True, force=True)
                logger.info(f"Container {self.id} removed successfully")
            except docker.errors.NotFound:
                logger.warning(
                    f"Container {self.id} not found, it may have been already removed"
                )
            except docker.errors.APIError as e:
                logger.error(f"Failed to remove container {self.id}: {str(e)}")
                raise SandboxException(
                    f"Failed to remove container {self.id}: {str(e)}"
                ) from e
            finally:
                self.container = None
        else:
            logger.warning(f"No container to remove for sandbox {self.id}")

    def get_hostname(self, port: Optional[int] = None) -> str:
        if not self.container:
            raise SandboxException("Container is not running")

        if port:
            return f"localhost:{self.container.ports[f'{port}/tcp'][0]['HostPort']}"
        return self.container.name

    async def keep_alive(self, duration: int):
        logger.info(f"Keeping sandbox {self.id} alive for {duration}ms")
        await asyncio.sleep(duration / 1000)

    @staticmethod
    async def list() -> List[Dict[str, Any]]:
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

    async def scan_ports(self) -> List[OpenPort]:
        # Implement port scanning logic here
        # This is a placeholder implementation
        result, _ = await self.communicate("netstat -tuln | grep LISTEN")
        ports = []
        for line in result.split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 4:
                    ip, port = parts[3].rsplit(":", 1)
                    ports.append(OpenPort(ip=ip, port=int(port), state="LISTEN"))
        return ports
