from typing import List, Optional, Dict, Any
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

    async def _get_docker_adapter(self):
        return self.docker_adapter

    async def build_custom_image(
        self, dockerfile: str, tag: str, build_args: Optional[Dict[str, str]] = None
    ) -> str:
        docker_adapter = await self._get_docker_adapter()
        return await docker_adapter.build_image(dockerfile, tag, build_args)

    async def sandboxes_get(self) -> List[RunningSandboxes]:
        logger.info("Listing all sandboxes")
        docker_adapter = await self._get_docker_adapter()
        return await docker_adapter.list_sandboxes()

    async def sandboxes_post(self, new_sandbox: NewSandbox) -> Sandbox:
        logger.info(f"Creating new sandbox with template: {new_sandbox.template_id}")
        docker_adapter = await self._get_docker_adapter()
        return await docker_adapter.create_sandbox(new_sandbox)

    async def sandboxes_sandbox_id_delete(self, sandbox_id: str) -> None:
        docker_adapter = await self._get_docker_adapter()
        await docker_adapter.delete_sandbox(sandbox_id)

    async def sandboxes_sandbox_id_logs_get(
        self, sandbox_id: str, start: Optional[int] = None, limit: Optional[int] = None
    ) -> SandboxLogs:
        docker_adapter = await self._get_docker_adapter()
        logs = await docker_adapter.get_sandbox_logs(sandbox_id, start, limit)
        return SandboxLogs(
            logs=[
                SandboxLog(timestamp=datetime.now(), line=line)
                for line in logs.splitlines()
            ]
        )

    async def sandboxes_sandbox_id_refreshes_post(
        self, sandbox_id: str, refresh_request
    ) -> None:
        docker_adapter = await self._get_docker_adapter()
        await docker_adapter.refresh_sandbox(sandbox_id, refresh_request.duration)

    async def upload_file(self, sandbox_id: str, content: bytes, container_path: str):
        docker_adapter = await self._get_docker_adapter()
        await docker_adapter.upload_file(sandbox_id, content, container_path)

    async def download_file(self, sandbox_id: str, container_path: str) -> bytes:
        docker_adapter = await self._get_docker_adapter()
        return await docker_adapter.download_file(sandbox_id, container_path)

    async def list_files(self, sandbox_id: str, path: str) -> List[Dict[str, str]]:
        docker_adapter = await self._get_docker_adapter()
        return await docker_adapter.list_files(sandbox_id, path)

    async def create_network(self, network_name: str) -> str:
        docker_adapter = await self._get_docker_adapter()
        return await docker_adapter.create_network(network_name)

    async def connect_to_network(self, sandbox_id: str, network_id: str):
        docker_adapter = await self._get_docker_adapter()
        await docker_adapter.connect_to_network(sandbox_id, network_id)

    async def disconnect_from_network(self, sandbox_id: str, network_id: str):
        docker_adapter = await self._get_docker_adapter()
        await docker_adapter.disconnect_from_network(sandbox_id, network_id)

    async def create_secret(self, name: str, data: str) -> str:
        docker_adapter = await self._get_docker_adapter()
        return await docker_adapter.create_secret(name, data)

    async def attach_secret_to_sandbox(
        self, sandbox_id: str, secret_id: str, target_file: str
    ):
        docker_adapter = await self._get_docker_adapter()
        await docker_adapter.attach_secret_to_sandbox(
            sandbox_id, secret_id, target_file
        )

    async def check_sandbox_health(self, sandbox_id: str) -> Dict[str, Any]:
        docker_adapter = await self._get_docker_adapter()
        return await docker_adapter.check_sandbox_health(sandbox_id)

    async def get_sandbox_stats(self, sandbox_id: str) -> Dict[str, Any]:
        docker_adapter = await self._get_docker_adapter()
        return await docker_adapter.get_sandbox_stats(sandbox_id)

    async def close(self):
        logger.info("Closing SandboxesApi")
        await self.docker_adapter.close()
