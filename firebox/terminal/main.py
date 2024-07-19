# In firebox/terminal/main.py

import asyncio
from typing import Any, Callable, Optional, Dict

from firebox.constants import TIMEOUT
from firebox.exception import TerminalException
from firebox.models import EnvVars, TerminalOutput
from firebox.utils.id import create_id
from firebox.logs import logger


class Terminal:
    def __init__(
        self,
        terminal_id: str,
        sandbox,
        on_data: Callable[[str], Any],
        on_exit: Optional[Callable[[], Any]] = None,
    ):
        self._terminal_id = terminal_id
        self._sandbox = sandbox
        self._on_data = on_data
        self._on_exit = on_exit
        self._output = TerminalOutput()
        self._finished = asyncio.Future()
        self._read_task = asyncio.create_task(self._read_output())

    async def _read_output(self):
        try:
            while not self._finished.done():
                result = await self._sandbox.communicate(
                    f"cat /tmp/terminal_{self._terminal_id}_output"
                )
                if result[0] == 0 and result[1]:
                    data = result[1]
                    self._output._add_data(data)
                    self._on_data(data)
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error reading from terminal: {str(e)}")
        finally:
            if self._on_exit:
                self._on_exit()

    async def send_data(self, data: str, timeout: Optional[float] = TIMEOUT) -> None:
        try:
            await self._sandbox.communicate(
                f"echo '{data}' >> /tmp/terminal_{self._terminal_id}_input",
                timeout=timeout,
            )
        except Exception as e:
            raise TerminalException(f"Failed to send data to terminal: {str(e)}") from e

    async def kill(self, timeout: Optional[float] = TIMEOUT) -> None:
        try:
            await self._sandbox.communicate(
                f"pkill -f 'terminal_{self._terminal_id}'", timeout=timeout
            )
            self._finished.set_result(None)
        except Exception as e:
            raise TerminalException(f"Failed to kill terminal: {str(e)}") from e


class TerminalManager:
    def __init__(self, sandbox):
        self._sandbox = sandbox

    async def start(
        self,
        on_data: Callable[[str], Any],
        cols: int,
        rows: int,
        cwd: str = "",
        terminal_id: Optional[str] = None,
        on_exit: Optional[Callable[[], Any]] = None,
        cmd: Optional[str] = None,
        env_vars: Optional[EnvVars] = None,
        timeout: Optional[float] = TIMEOUT,
    ) -> Terminal:
        terminal_id = terminal_id or create_id(12)

        if not cwd and self._sandbox.cwd:
            cwd = self._sandbox.cwd

        env_vars_str = " ".join(f"{k}={v}" for k, v in (env_vars or {}).items())

        # Start a background process in the sandbox to simulate a terminal
        terminal_cmd = f'while true; do if [ -f /tmp/terminal_{terminal_id}_input ]; then bash -c "$(cat /tmp/terminal_{terminal_id}_input)"; > /tmp/terminal_{terminal_id}_input; fi; sleep 0.1; done > /tmp/terminal_{terminal_id}_output 2>&1 &'
        await self._sandbox.communicate(f"{env_vars_str} cd {cwd} && {terminal_cmd}")

        if cmd:
            await self._sandbox.communicate(
                f"echo '{cmd}' > /tmp/terminal_{terminal_id}_input"
            )

        terminal = Terminal(
            terminal_id=terminal_id,
            sandbox=self._sandbox,
            on_data=on_data,
            on_exit=on_exit,
        )

        return terminal
