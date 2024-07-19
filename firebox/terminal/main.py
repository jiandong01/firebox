import asyncio
import pty
import os
from typing import Optional, Callable, Any

from ..exceptions import TerminalException


class Terminal:
    def __init__(
        self,
        sandbox,
        terminal_id: str,
        on_data: Callable[[str], Any],
        cols: int,
        rows: int,
        cwd: str = "",
        env_vars: Optional[dict] = None,
    ):
        self.sandbox = sandbox
        self.terminal_id = terminal_id
        self.on_data = on_data
        self.cols = cols
        self.rows = rows
        self.cwd = cwd
        self.env_vars = env_vars or {}
        self.master_fd = None
        self.slave_fd = None
        self.process = None

    async def start(self):
        self.master_fd, self.slave_fd = pty.openpty()
        env = {**os.environ, **self.env_vars}
        self.process = await asyncio.create_subprocess_shell(
            "bash",
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            env=env,
            cwd=self.cwd,
            start_new_session=True,
        )
        asyncio.create_task(self._read_output())

    async def _read_output(self):
        while True:
            try:
                data = os.read(self.master_fd, 1024).decode()
                if not data:
                    break
                self.on_data(data)
            except OSError:
                break

    async def send_data(self, data: str):
        if not self.master_fd:
            raise TerminalException("Terminal is not started")
        os.write(self.master_fd, data.encode())

    async def resize(self, cols: int, rows: int):
        import fcntl
        import termios
        import struct

        if not self.master_fd:
            raise TerminalException("Terminal is not started")

        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

    async def kill(self):
        if self.process:
            self.process.terminate()
            await self.process.wait()
        if self.master_fd:
            os.close(self.master_fd)
        if self.slave_fd:
            os.close(self.slave_fd)


class TerminalManager:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.terminals = {}

    async def start(
        self,
        on_data: Callable[[str], Any],
        cols: int,
        rows: int,
        cwd: str = "",
        terminal_id: Optional[str] = None,
        env_vars: Optional[dict] = None,
    ) -> Terminal:
        terminal_id = terminal_id or f"term_{len(self.terminals)}"
        terminal = Terminal(
            self.sandbox,
            terminal_id,
            on_data,
            cols,
            rows,
            cwd,
            env_vars,
        )
        await terminal.start()
        self.terminals[terminal_id] = terminal
        return terminal

    async def get(self, terminal_id: str) -> Optional[Terminal]:
        return self.terminals.get(terminal_id)

    async def close(self, terminal_id: str):
        terminal = self.terminals.get(terminal_id)
        if terminal:
            await terminal.kill()
            del self.terminals[terminal_id]
