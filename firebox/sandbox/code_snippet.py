# firebox/sandbox/code_snippet.py

from typing import Any, Callable, List, Optional
from pydantic import BaseModel

from firebox.sandbox.exception import MultipleExceptions, RpcException, SandboxException
from firebox.sandbox.sandbox_connection import SandboxConnection, SubscriptionArgs


class OpenPort(BaseModel):
    ip: str
    port: int
    state: str


class CodeSnippetManager:
    def __init__(
        self,
        sandbox: SandboxConnection,
        on_scan_ports: Optional[Callable[[List[OpenPort]], Any]] = None,
    ):
        self._sandbox = sandbox
        self.on_scan_ports = on_scan_ports

    def _subscribe(self):
        def on_scan_ports(ports: List[dict]):
            ports = [
                OpenPort(ip=port["Ip"], port=port["Port"], state=port["State"])
                for port in ports
            ]
            if self.on_scan_ports:
                self.on_scan_ports(ports)

        if self.on_scan_ports:
            try:
                self._sandbox._handle_subscriptions(
                    SubscriptionArgs(
                        service="codeSnippet",
                        handler=on_scan_ports,
                        method="scanOpenedPorts",
                    )
                )
            except RpcException as e:
                raise SandboxException(e.message) from e
            except MultipleExceptions as e:
                raise SandboxException("Failed to subscribe to RPC services") from e

        return self
