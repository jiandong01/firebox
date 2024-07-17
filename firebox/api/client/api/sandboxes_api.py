import docker
from typing import List, Optional
from ..models import Sandbox, NewSandbox, RunningSandboxes, SandboxLogs, SandboxLog


class SandboxesApi:
    def __init__(self, api_client=None):
        self.api_client = api_client or docker.from_env()

    def sandboxes_get(self) -> List[RunningSandboxes]:
        containers = self.api_client.containers.list()
        return [
            RunningSandboxes(
                template_id=(
                    container.image.tags[0] if container.image.tags else "unknown"
                ),
                sandbox_id=container.id[:12],
                client_id="local",
                started_at=container.attrs["Created"],
                cpu_count=container.attrs["HostConfig"]["NanoCpus"] // 1e9,
                memory_mb=container.attrs["HostConfig"]["Memory"] // (1024 * 1024),
                metadata=container.labels,
            )
            for container in containers
        ]

    def sandboxes_post(self, new_sandbox: NewSandbox) -> Sandbox:
        container = self.api_client.containers.run(
            new_sandbox.template_id,
            detach=True,
            environment=new_sandbox.metadata,
        )
        return Sandbox(
            template_id=new_sandbox.template_id,
            sandbox_id=container.id[:12],
            client_id="local",
            alias=new_sandbox.metadata.get("alias") if new_sandbox.metadata else None,
        )

    def sandboxes_sandbox_id_delete(self, sandbox_id: str) -> None:
        container = self.api_client.containers.get(sandbox_id)
        container.remove(force=True)

    def sandboxes_sandbox_id_logs_get(
        self, sandbox_id: str, start: Optional[int] = None, limit: Optional[int] = None
    ) -> SandboxLogs:
        container = self.api_client.containers.get(sandbox_id)
        logs = container.logs(since=start, tail=limit).decode("utf-8").splitlines()
        return SandboxLogs(logs=[SandboxLog(timestamp=0, line=line) for line in logs])

    def sandboxes_sandbox_id_refreshes_post(
        self, sandbox_id: str, refresh_request
    ) -> None:
        # This method can be a no-op for Docker-based implementation
        pass
