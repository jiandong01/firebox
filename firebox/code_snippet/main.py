import asyncio
from typing import Any, Callable, ClassVar, List, Optional
import json

from firebox.models import OpenPort, CodeSnippet
from firebox.exception import SandboxException
from firebox.constants import TIMEOUT
from firebox.logs import logger


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
            exit_code, output = await self.sandbox.communicate(
                "netstat -tuln | grep LISTEN", timeout=TIMEOUT
            )
            if exit_code != 0:
                raise Exception(f"Failed to scan ports: {output}")

            ports = []
            for line in output.split("\n"):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        ip, port = parts[3].rsplit(":", 1)
                        ports.append(OpenPort(ip=ip, port=int(port), state="LISTEN"))
            return ports
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
            script_path = f"/root/commands/{name}"
            escaped_content = content.replace('"', '\\"')
            exit_code, output = await self.sandbox.communicate(
                f'echo "{escaped_content}" > {script_path} && chmod +x {script_path}',
                timeout=timeout,
            )
            if exit_code != 0:
                raise Exception(f"Failed to add script: {output}")
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
            script_path = f"/root/commands/{name}"
            exit_code, output = await self.sandbox.communicate(
                f"rm -f {script_path}", timeout=timeout
            )
            if exit_code != 0:
                raise Exception(f"Failed to remove script: {output}")
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
            exit_code, output = await self.sandbox.communicate(
                "ls -1 /root/commands", timeout=timeout
            )
            if exit_code != 0:
                raise Exception(f"Failed to list scripts: {output}")

            scripts = []
            for name in output.split("\n"):
                if name.strip():
                    content = await self.get_script_content(name, timeout)
                    scripts.append(CodeSnippet(name=name, content=content))
            return scripts
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
            content = await self.get_script_content(name, timeout)
            return CodeSnippet(name=name, content=content)
        except Exception as e:
            raise SandboxException(f"Failed to get script {name}: {str(e)}") from e

    async def get_script_content(
        self, name: str, timeout: Optional[float] = TIMEOUT
    ) -> str:
        """
        Get the content of a specific script.

        :param name: Name of the script
        :param timeout: Timeout for the operation
        :return: Content of the script
        """
        script_path = f"/root/commands/{name}"
        exit_code, output = await self.sandbox.communicate(
            f"cat {script_path}", timeout=timeout
        )
        if exit_code != 0:
            raise Exception(f"Failed to read script content: {output}")
        return output
