import docker
from typing import List, Optional
from datetime import datetime
from .models import Sandbox, NewSandbox, RunningSandboxes, SandboxLogs, SandboxLog
from .docker_adapter import DockerAdapter


class SandboxesApi:
    def __init__(self, configuration=None):
        self.docker_adapter = DockerAdapter()

    def sandboxes_get(self) -> List[RunningSandboxes]:
        return self.docker_adapter.list_sandboxes()

    def sandboxes_post(self, new_sandbox: NewSandbox) -> Sandbox:
        return self.docker_adapter.create_sandbox(new_sandbox)

    def sandboxes_sandbox_id_delete(self, sandbox_id: str) -> None:
        self.docker_adapter.delete_sandbox(sandbox_id)

    def sandboxes_sandbox_id_logs_get(
        self, sandbox_id: str, start: Optional[int] = None, limit: Optional[int] = None
    ) -> SandboxLogs:
        logs = self.docker_adapter.get_sandbox_logs(sandbox_id, start, limit)
        return SandboxLogs(
            logs=[
                SandboxLog(timestamp=datetime.now(), line=line)
                for line in logs.splitlines()
            ]
        )

    def sandboxes_sandbox_id_refreshes_post(
        self, sandbox_id: str, refresh_request
    ) -> None:
        # This method can be a no-op for Docker-based implementation
        pass
