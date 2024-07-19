import asyncio
import logging
from typing import Any, Callable, ClassVar, List, Optional

from firebox.models import OpenPort, CodeSnippet
from firebox.exception import SandboxException
from firebox.constants import TIMEOUT

logger = logging.getLogger(__name__)


ScanOpenedPortsHandler = Callable[[List[OpenPort]], Any]


class CodeSnippetManager:
    service_name: ClassVar[str] = "codeSnippet"

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
                raise SandboxException("Failed to subscribe to port scanning") from e

    async def _subscribe_to_port_scanning(self):
        async def port_scanner():
            while True:
                ports = await self._scan_ports()
                if self.on_scan_ports:
                    self.on_scan_ports(ports)
                await asyncio.sleep(10)  # Scan every 10 seconds

        asyncio.create_task(port_scanner())

    async def _scan_ports(self) -> List[OpenPort]:
        try:
            result = await self.sandbox._call(
                self.service_name, "scanOpenedPorts", timeout=TIMEOUT
            )
            return [OpenPort(**port) for port in result]
        except Exception as e:
            logger.error(f"Failed to scan ports: {str(e)}")
            return []

    async def add_script(
        self, name: str, content: str, timeout: Optional[float] = TIMEOUT
    ) -> None:
        """
        Add a custom script to the sandbox.

        :param name: Name of the script
        :param content: Content of the script
        :param timeout: Timeout for the operation
        """
        try:
            await self.sandbox._call(
                self.service_name, "addScript", [name, content], timeout=timeout
            )
            logger.info(f"Added script: {name}")
        except Exception as e:
            raise SandboxException(f"Failed to add script {name}: {str(e)}") from e

    async def remove_script(
        self, name: str, timeout: Optional[float] = TIMEOUT
    ) -> None:
        """
        Remove a custom script from the sandbox.

        :param name: Name of the script to remove
        :param timeout: Timeout for the operation
        """
        try:
            await self.sandbox._call(
                self.service_name, "removeScript", [name], timeout=timeout
            )
            logger.info(f"Removed script: {name}")
        except Exception as e:
            raise SandboxException(f"Failed to remove script {name}: {str(e)}") from e

    async def list_scripts(
        self, timeout: Optional[float] = TIMEOUT
    ) -> List[CodeSnippet]:
        """
        List all custom scripts in the sandbox.

        :param timeout: Timeout for the operation
        :return: List of CodeSnippet objects
        """
        try:
            result = await self.sandbox._call(
                self.service_name, "listScripts", timeout=timeout
            )
            return [CodeSnippet(**script) for script in result]
        except Exception as e:
            raise SandboxException(f"Failed to list scripts: {str(e)}") from e

    async def get_script(
        self, name: str, timeout: Optional[float] = TIMEOUT
    ) -> CodeSnippet:
        """
        Get a specific custom script from the sandbox.

        :param name: Name of the script to retrieve
        :param timeout: Timeout for the operation
        :return: CodeSnippet object
        """
        try:
            result = await self.sandbox._call(
                self.service_name, "getScript", [name], timeout=timeout
            )
            return CodeSnippet(**result)
        except Exception as e:
            raise SandboxException(f"Failed to get script {name}: {str(e)}") from e
