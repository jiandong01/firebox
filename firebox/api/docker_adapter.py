import docker
from typing import Dict, Optional, List
from firebox.api.models import Sandbox, NewSandbox, RunningSandboxes
from firebox.exceptions import (
    DockerOperationError,
    SandboxCreationError,
    SandboxNotFoundError,
)


class DockerAdapter:
    def __init__(self):
        self.client = docker.from_env()

    def create_sandbox(self, new_sandbox: NewSandbox) -> Sandbox:

        try:
            container_config = {
                "image": new_sandbox.template_id,
                "detach": True,
                "environment": new_sandbox.metadata,
                "volumes": {},  # Will be populated from new_sandbox
                "ports": {},  # Will be populated from new_sandbox
                "cpu_count": new_sandbox.cpu_count,
                "mem_limit": f"{new_sandbox.memory_mb}m",
            }

            # Add volume mounts
            if new_sandbox.volumes:
                for host_path, container_path in new_sandbox.volumes.items():
                    container_config["volumes"][host_path] = {
                        "bind": container_path,
                        "mode": "rw",
                    }

            # Add port mappings
            if new_sandbox.ports:
                for container_port, host_port in new_sandbox.ports.items():
                    container_config["ports"][container_port] = host_port

            container = self.client.containers.run(**container_config)

            return Sandbox(
                template_id=new_sandbox.template_id,
                sandbox_id=container.id[:12],
                client_id="local",
                alias=(
                    new_sandbox.metadata.get("alias") if new_sandbox.metadata else None
                ),
            )

        except docker.errors.APIError as e:
            raise SandboxCreationError(f"Failed to create sandbox: {str(e)}")

    def list_sandboxes(self) -> List[RunningSandboxes]:
        containers = self.client.containers.list()
        return [
            RunningSandboxes(
                templateID=(
                    container.image.tags[0] if container.image.tags else "unknown"
                ),
                sandboxID=container.id[:12],
                clientID="local",
                startedAt=container.attrs["Created"],
                cpuCount=container.attrs["HostConfig"]["NanoCpus"] // 1e9,
                memoryMB=container.attrs["HostConfig"]["Memory"] // (1024 * 1024),
                metadata=container.labels,
            )
            for container in containers
        ]

    def delete_sandbox(self, sandbox_id: str):
        try:
            container = self.client.containers.get(sandbox_id)
            container.remove(force=True)
        except docker.errors.NotFound:
            raise SandboxNotFoundError(f"Sandbox with ID {sandbox_id} not found")
        except docker.errors.APIError as e:
            raise DockerOperationError(f"Failed to delete sandbox: {str(e)}")

    def refresh_sandbox(self, sandbox_id: str, duration: int):
        # For Docker, we don't need to refresh. This method can be a no-op.
        pass

    def get_sandbox_logs(
        self, sandbox_id: str, start: Optional[int] = None, limit: Optional[int] = None
    ) -> str:
        container = self.client.containers.get(sandbox_id)
        return container.logs(since=start, tail=limit).decode("utf-8")
