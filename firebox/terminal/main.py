import asyncio
import logging
import pty
import os
import fcntl
import termios
import struct
from typing import Any, Callable, Optional, Dict

from firebox.constants import TIMEOUT
from firebox.exception import TerminalException
from firebox.models import EnvVars, TerminalOutput
from firebox.utils.id import create_id

logger = logging.getLogger(__name__)


class Terminal:
    """
    Terminal session.
    """

    @property
    def data(self) -> str:
        """
        Terminal output data.
        """
        return self._output.data

    @property
    def output(self) -> TerminalOutput:
        """
        Terminal output.
        """
        return self._output

    @property
    def finished(self):
        """
        A future that is resolved when the terminal session exits.
        """
        return self._finished

    @property
    def terminal_id(self) -> str:
        """
        The terminal id used to identify the terminal in the session.
        """
        return self._terminal_id

    def __init__(
        self,
        terminal_id: str,
        sandbox,
        master_fd: int,
        slave_fd: int,
        process: asyncio.subprocess.Process,
        on_data: Callable[[str], Any],
        on_exit: Optional[Callable[[], Any]],
    ):
        self._terminal_id = terminal_id
        self._sandbox = sandbox
        self._master_fd = master_fd
        self._slave_fd = slave_fd
        self._process = process
        self._on_data = on_data
        self._on_exit = on_exit
        self._output = TerminalOutput()
        self._finished = asyncio.Future()
        self._read_task = asyncio.create_task(self._read_output())

    async def _read_output(self):
        try:
            while True:
                data = await self._sandbox.loop.run_in_executor(
                    None, os.read, self._master_fd, 1024
                )
                if not data:
                    break
                decoded_data = data.decode()
                self._output._add_data(decoded_data)
                self._on_data(decoded_data)
        except Exception as e:
            logger.error(f"Error reading from terminal: {str(e)}")
        finally:
            self._finished.set_result(None)
            if self._on_exit:
                self._on_exit()

    async def wait(self):
        """
        Wait till the terminal session exits.
        """
        return await self._finished

    async def send_data(self, data: str, timeout: Optional[float] = TIMEOUT) -> None:
        """
        Send data to the terminal standard input.

        :param data: Data to send
        :param timeout: Specify the duration, in seconds to give the method to finish its execution before it times out
        """
        try:
            await self._sandbox.loop.run_in_executor(
                None, os.write, self._master_fd, data.encode()
            )
        except Exception as e:
            raise TerminalException(f"Failed to send data to terminal: {str(e)}") from e

    async def resize(
        self, cols: int, rows: int, timeout: Optional[float] = TIMEOUT
    ) -> None:
        """
        Resizes the terminal tty.

        :param cols: Number of columns
        :param rows: Number of rows
        :param timeout: Specify the duration, in seconds to give the method to finish its execution before it times out
        """
        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            await self._sandbox.loop.run_in_executor(
                None, fcntl.ioctl, self._master_fd, termios.TIOCSWINSZ, winsize
            )
        except Exception as e:
            raise TerminalException(f"Failed to resize terminal: {str(e)}") from e

    async def kill(self, timeout: Optional[float] = TIMEOUT) -> None:
        """
        Kill the terminal session.

        :param timeout: Specify the duration, in seconds to give the method to finish its execution before it times out
        """
        try:
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._process.kill()
        except Exception as e:
            raise TerminalException(f"Failed to kill terminal: {str(e)}") from e
        finally:
            os.close(self._master_fd)
            os.close(self._slave_fd)
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass


class TerminalManager:
    """
    Manager for starting and interacting with terminal sessions in the sandbox.
    """

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
        """
        Start a new terminal session.

        :param on_data: Callback that will be called when the terminal sends data
        :param cwd: Working directory where will the terminal start
        :param terminal_id: Unique identifier of the terminal session
        :param on_exit: Callback that will be called when the terminal exits
        :param cols: Number of columns the terminal will have. This affects rendering
        :param rows: Number of rows the terminal will have. This affects rendering
        :param cmd: If the `cmd` parameter is defined it will be executed as a command
        and this terminal session will exit when the command exits
        :param env_vars: Environment variables that will be accessible inside of the terminal
        :param timeout: Specify the duration, in seconds to give the method to finish its execution before it times out

        :return: Terminal session
        """
        env_vars = {**self._sandbox.env_vars, **(env_vars or {})}
        terminal_id = terminal_id or create_id(12)

        if not cwd and self._sandbox.cwd:
            cwd = self._sandbox.cwd

        master_fd, slave_fd = pty.openpty()

        # Set the terminal size
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

        cmd = cmd or "bash"
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env_vars,
            cwd=cwd,
            start_new_session=True,
        )

        terminal = Terminal(
            terminal_id=terminal_id,
            sandbox=self._sandbox,
            master_fd=master_fd,
            slave_fd=slave_fd,
            process=process,
            on_data=on_data,
            on_exit=on_exit,
        )

        return terminal
