import asyncio
import logging
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
        trigger_exit: Callable[[], Any],
        finished: asyncio.Future,
        output: TerminalOutput,
    ):
        self._terminal_id = terminal_id
        self._sandbox = sandbox
        self._trigger_exit = trigger_exit
        self._finished = finished
        self._output = output

    async def wait(self):
        """
        Wait till the terminal session exits.
        """
        return await self.finished

    async def send_data(self, data: str, timeout: Optional[float] = TIMEOUT) -> None:
        """
        Send data to the terminal standard input.

        :param data: Data to send
        :param timeout: Specify the duration, in seconds to give the method to finish its execution before it times out
        """
        try:
            await self._sandbox._call(
                TerminalManager._service_name,
                "data",
                [self.terminal_id, data],
                timeout=timeout,
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
            await self._sandbox._call(
                TerminalManager._service_name,
                "resize",
                [self.terminal_id, cols, rows],
                timeout=timeout,
            )
        except Exception as e:
            raise TerminalException(f"Failed to resize terminal: {str(e)}") from e

    async def kill(self, timeout: Optional[float] = TIMEOUT) -> None:
        """
        Kill the terminal session.

        :param timeout: Specify the duration, in seconds to give the method to finish its execution before it times out
        """
        try:
            await self._sandbox._call(
                TerminalManager._service_name,
                "destroy",
                [self.terminal_id],
                timeout=timeout,
            )
        except Exception as e:
            raise TerminalException(f"Failed to kill terminal: {str(e)}") from e
        self._trigger_exit()


class TerminalManager:
    """
    Manager for starting and interacting with terminal sessions in the sandbox.
    """

    _service_name = "terminal"

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

        future_exit = asyncio.Future()
        terminal_id = terminal_id or create_id(12)

        output = TerminalOutput()

        def handle_data(data: str):
            output._add_data(data)
            on_data(data)

        try:
            unsub_all = await self._sandbox._handle_subscriptions(
                SubscriptionArgs(
                    service=self._service_name,
                    handler=handle_data,
                    method="onData",
                    params=[terminal_id],
                ),
                SubscriptionArgs(
                    service=self._service_name,
                    handler=lambda result: future_exit.set_result(result),
                    method="onExit",
                    params=[terminal_id],
                ),
            )
        except Exception as e:
            future_exit.cancel()
            raise TerminalException("Failed to subscribe to terminal events") from e

        future_exit_handler_finish: asyncio.Future[TerminalOutput] = asyncio.Future()

        def exit_handler():
            future_exit.result()

            if unsub_all:
                unsub_all()

            if on_exit:
                on_exit()
            future_exit_handler_finish.set_result(output)

        asyncio.create_task(exit_handler())

        def trigger_exit():
            future_exit.set_result(None)
            return future_exit_handler_finish.result()

        try:
            if not cwd and self._sandbox.cwd:
                cwd = self._sandbox.cwd

            await self._sandbox._call(
                self._service_name,
                "start",
                [
                    terminal_id,
                    cols,
                    rows,
                    env_vars,
                    cmd,
                    cwd,
                ],
                timeout=timeout,
            )
            return Terminal(
                terminal_id=terminal_id,
                sandbox=self._sandbox,
                trigger_exit=trigger_exit,
                finished=future_exit_handler_finish,
                output=output,
            )
        except Exception as e:
            trigger_exit()
            raise TerminalException(f"Failed to start terminal: {str(e)}") from e
