import asyncio
import time
import logging
from typing import Dict, Optional, Any, List, Callable, Union

from ..exception import (
    ProcessException,
    TimeoutException,
    CurrentWorkingDirectoryDoesntExistException,
)
from ..models import EnvVars, ProcessMessage, ProcessOutput
from ..constants import TIMEOUT

logger = logging.getLogger(__name__)


class Process:
    def __init__(
        self,
        process_id: str,
        sandbox,
        trigger_exit: Callable[[], Any],
        finished: asyncio.Future,
        output: ProcessOutput,
    ):
        self._process_id = process_id
        self._sandbox = sandbox
        self._trigger_exit = trigger_exit
        self._finished = finished
        self._output = output

    @property
    def exit_code(self) -> Optional[int]:
        if not self.finished:
            raise ProcessException("Process has not finished yet")
        return self.output.exit_code

    @property
    def output(self) -> ProcessOutput:
        return self._output

    @property
    def stdout(self) -> str:
        return self._output.stdout

    @property
    def stderr(self) -> str:
        return self._output.stderr

    @property
    def error(self) -> bool:
        return self._output.error

    @property
    def output_messages(self) -> List[ProcessMessage]:
        return self._output.messages

    @property
    def finished(self):
        return self._finished

    @property
    def process_id(self) -> str:
        return self._process_id

    async def wait(self, timeout: Optional[float] = None) -> ProcessOutput:
        try:
            await asyncio.wait_for(self._finished, timeout=timeout)
            return self._output
        except asyncio.TimeoutException:
            raise TimeoutException(f"Process did not finish within {timeout} seconds")

    async def send_stdin(self, data: str, timeout: Optional[float] = TIMEOUT) -> None:
        try:
            await self._sandbox._call(
                ProcessManager._service_name,
                "stdin",
                [self.process_id, data],
                timeout=timeout,
            )
        except Exception as e:
            raise ProcessException(f"Failed to send stdin: {str(e)}") from e

    async def kill(self, timeout: Optional[float] = TIMEOUT) -> None:
        try:
            await self._sandbox._call(
                ProcessManager._service_name, "kill", [self.process_id], timeout=timeout
            )
        except Exception as e:
            raise ProcessException(f"Failed to kill process: {str(e)}") from e
        self._trigger_exit()


class ProcessManager:
    _service_name = "process"

    def __init__(
        self,
        sandbox,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Union[Callable[[int], Any], Callable[[], Any]]] = None,
    ):
        self._sandbox = sandbox
        self._on_stdout = on_stdout
        self._on_stderr = on_stderr
        self._on_exit = on_exit

    async def start(
        self,
        cmd: str,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Union[Callable[[int], Any], Callable[[], Any]]] = None,
        env_vars: Optional[EnvVars] = None,
        cwd: str = "",
        process_id: Optional[str] = None,
        timeout: Optional[float] = TIMEOUT,
    ) -> Process:
        logger.info(f"Starting process: {cmd}")
        env_vars = env_vars or {}
        env_vars = {**self._sandbox.env_vars, **env_vars}

        on_stdout = on_stdout or self._on_stdout
        on_stderr = on_stderr or self._on_stderr
        on_exit = on_exit or self._on_exit

        future_exit = asyncio.Future()
        process_id = process_id or f"process_{int(time.time() * 1000)}"

        output = ProcessOutput()

        def handle_exit(exit_code: int):
            output.exit_code = exit_code
            logger.info(f"Process {process_id} exited with exit code {exit_code}")
            if not future_exit.done():
                future_exit.set_result(True)

        def handle_stdout(data: Dict[str, Any]):
            message = ProcessMessage(
                line=data["line"],
                timestamp=data["timestamp"],
                error=False,
            )
            output._add_stdout(message)
            if on_stdout:
                on_stdout(message)

        def handle_stderr(data: Dict[str, Any]):
            message = ProcessMessage(
                line=data["line"],
                timestamp=data["timestamp"],
                error=True,
            )
            output._add_stderr(message)
            if on_stderr:
                on_stderr(message)

        try:
            unsub_all = await self._sandbox._handle_subscriptions(
                self._service_name,
                handle_exit,
                "onExit",
                [process_id],
                self._service_name,
                handle_stdout,
                "onStdout",
                [process_id],
                self._service_name,
                handle_stderr,
                "onStderr",
                [process_id],
            )
        except Exception as e:
            raise ProcessException("Failed to subscribe to process events") from e

        future_exit_handler_finish = asyncio.Future()

        def exit_handler():
            future_exit.result()
            logger.info(f"Handling process exit (id: {process_id})")
            unsub_all()
            if on_exit:
                try:
                    on_exit(output.exit_code or 0)
                except Exception as error:
                    logger.exception(f"Error in on_exit callback: {error}")
            future_exit_handler_finish.set_result(output)

        asyncio.create_task(exit_handler())

        def trigger_exit():
            logger.info(f"Exiting the process (id: {process_id})")
            if not future_exit.done():
                future_exit.set_result(None)
            future_exit_handler_finish.result()

        try:
            if not cwd and self._sandbox.cwd:
                cwd = self._sandbox.cwd

            await self._sandbox._call(
                self._service_name,
                "start",
                [
                    process_id,
                    cmd,
                    env_vars,
                    cwd,
                ],
                timeout=timeout,
            )
            logger.info(f"Started process (id: {process_id})")
            return Process(
                output=output,
                sandbox=self._sandbox,
                process_id=process_id,
                trigger_exit=trigger_exit,
                finished=future_exit_handler_finish,
            )
        except Exception as e:
            trigger_exit()
            if "no such file or directory" in str(e).lower():
                raise CurrentWorkingDirectoryDoesntExistException(
                    "Failed to start the process. You are trying to set `cwd` to a directory that does not exist."
                ) from e
            raise ProcessException(f"Failed to start process: {str(e)}") from e

    async def start_and_wait(
        self,
        cmd: str,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Callable[[int], Any]] = None,
        env_vars: Optional[EnvVars] = None,
        cwd: str = "",
        process_id: Optional[str] = None,
        timeout: Optional[float] = TIMEOUT,
    ) -> ProcessOutput:
        process = await self.start(
            cmd,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            on_exit=on_exit,
            env_vars=env_vars,
            cwd=cwd,
            process_id=process_id,
            timeout=timeout,
        )
        return await process.wait(timeout)
