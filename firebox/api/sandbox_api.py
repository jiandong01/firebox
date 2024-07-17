from typing import List, Optional, Dict
from datetime import datetime
from firebox.api.models import (
    Sandbox,
    NewSandbox,
    RunningSandboxes,
    SandboxLogs,
    SandboxLog,
)
from firebox.api.async_docker_adapter import AsyncDockerAdapter
from firebox.config import config
from firebox.logging import logger
from firebox.cleanup import cleanup_manager


class SandboxesApi:
    def __init__(self):
        self.docker_adapter = AsyncDockerAdapter()
        cleanup_manager.add_task(self.close)

    async def build_custom_image(
        self, dockerfile: str, tag: str, build_args: Optional[Dict[str, str]] = None
    ) -> str:
        return await self.docker_adapter.build_image(dockerfile, tag, build_args)

    async def sandboxes_get(self) -> List[RunningSandboxes]:
        logger.info("Listing all sandboxes")
        return await self.docker_adapter.list_sandboxes()

    async def sandboxes_post(self, new_sandbox: NewSandbox) -> Sandbox:
        logger.info(f"Creating new sandbox with template: {new_sandbox.template_id}")
        return await self.docker_adapter.create_sandbox(new_sandbox)

    async def sandboxes_sandbox_id_delete(self, sandbox_id: str) -> None:
        await self.docker_adapter.delete_sandbox(sandbox_id)

    async def sandboxes_sandbox_id_logs_get(
        self, sandbox_id: str, start: Optional[int] = None, limit: Optional[int] = None
    ) -> SandboxLogs:
        logs = await self.docker_adapter.get_sandbox_logs(sandbox_id, start, limit)
        return SandboxLogs(
            logs=[
                SandboxLog(timestamp=datetime.now(), line=line)
                for line in logs.splitlines()
            ]
        )

    async def sandboxes_sandbox_id_refreshes_post(
        self, sandbox_id: str, refresh_request
    ) -> None:
        # This method can be a no-op for Docker-based implementation
        await self.docker_adapter.refresh_sandbox(sandbox_id, refresh_request.duration)

    async def upload_file(self, sandbox_id: str, local_path: str, container_path: str):
        await self.docker_adapter.upload_file(sandbox_id, local_path, container_path)

    async def download_file(
        self, sandbox_id: str, container_path: str, local_path: str
    ):
        await self.docker_adapter.download_file(sandbox_id, container_path, local_path)

    async def create_network(self, network_name: str) -> str:
        return await self.docker_adapter.create_network(network_name)

    async def connect_to_network(self, sandbox_id: str, network_id: str):
        await self.docker_adapter.connect_to_network(sandbox_id, network_id)

    async def disconnect_from_network(self, sandbox_id: str, network_id: str):
        await self.docker_adapter.disconnect_from_network(sandbox_id, network_id)

    async def create_secret(self, name: str, data: str) -> str:
        return await self.docker_adapter.create_secret(name, data)

    async def attach_secret_to_sandbox(
        self, sandbox_id: str, secret_id: str, target_file: str
    ):
        await self.docker_adapter.attach_secret_to_sandbox(
            sandbox_id, secret_id, target_file
        )

    async def close(self):
        logger.info("Closing SandboxesApi")
        await self.docker_adapter.close()
