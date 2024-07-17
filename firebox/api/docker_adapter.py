import docker
from typing import Dict, Optional, List
from firebox.api.client.models import Sandbox, NewSandbox, RunningSandboxes


class DockerAdapter:
    def __init__(self):
        self.client = docker.from_env()

    def create_sandbox(self, new_sandbox: NewSandbox) -> Sandbox:
        container = self.client.containers.run(
            new_sandbox.templateID,
            detach=True,
            environment=new_sandbox.metadata,
        )
        return Sandbox(
            templateID=new_sandbox.templateID,
            sandboxID=container.id[:12],  # Use first 12 chars of container ID
            clientID="local",
            alias=new_sandbox.metadata.get("alias") if new_sandbox.metadata else None,
        )

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
        container = self.client.containers.get(sandbox_id)
        container.remove(force=True)

    def refresh_sandbox(self, sandbox_id: str, duration: int):
        # For Docker, we don't need to refresh. This method can be a no-op.
        pass

    def get_sandbox_logs(
        self, sandbox_id: str, start: Optional[int] = None, limit: Optional[int] = None
    ) -> str:
        container = self.client.containers.get(sandbox_id)
        return container.logs(since=start, tail=limit).decode("utf-8")
