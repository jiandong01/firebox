from typing import Any, Callable, List, Optional
from pydantic import BaseModel
import asyncio

from ..exceptions import SandboxError


class OpenPort(BaseModel):
    ip: str
    port: int
    state: str


ScanOpenedPortsHandler = Callable[[List[OpenPort]], Any]


class CodeSnippetManager:
    def __init__(
        self,
        sandbox,
        on_scan_ports: Optional[ScanOpenedPortsHandler] = None,
    ):
        self.sandbox = sandbox
        self.on_scan_ports = on_scan_ports

    async def subscribe(self):
        if self.on_scan_ports:
            try:
                await self._subscribe_to_port_scanning()
            except Exception as e:
                raise SandboxError("Failed to subscribe to port scanning") from e

    async def _subscribe_to_port_scanning(self):
        async def port_scanner():
            while True:
                ports = await self._scan_ports()
                if self.on_scan_ports:
                    self.on_scan_ports(ports)
                await asyncio.sleep(10)  # Scan every 10 seconds

        asyncio.create_task(port_scanner())

    async def _scan_ports(self) -> List[OpenPort]:
        # Implement port scanning logic here
        # This is a placeholder implementation
        result, _ = await self.sandbox.communicate("netstat -tuln | grep LISTEN")
        ports = []
        for line in result.split("\n"):
            if line.strip():
                parts = line.split()
                if len(parts) >= 4:
                    ip, port = parts[3].rsplit(":", 1)
                    ports.append(OpenPort(ip=ip, port=int(port), state="LISTEN"))
        return ports

    async def add_script(self, name: str, content: str) -> None:
        """Add a custom script to the sandbox."""
        script_path = f"/root/commands/{name}"
        escaped_content = content.replace('"', '\\"')
        command = f'echo "{escaped_content}" > {script_path} && chmod +x {script_path}'
        await self.sandbox.communicate(command)
