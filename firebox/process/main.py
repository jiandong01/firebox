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
        cmd: str,
        env_vars: Dict[str, str],
        cwd: str,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Union[Callable[[int], Any], Callable[[], Any]]] = None,
    ):
        self._process_id = process_id
        self._sandbox = sandbox
        self._cmd = cmd
        self._env_vars = env_vars
        self._cwd = cwd
        self._on_stdout = on_stdout
        self._on_stderr = on_stderr
        self._on_exit = on_exit
        self._output = ProcessOutput()
        self._finished = asyncio.Future()
        self._task = None

    @property
    def exit_code(self) -> Optional[int]:
        if not self._finished.done():
            raise ProcessException("Process has not finished yet")
        return self._output.exit_code

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

    async def start(self):
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        try:
            env_vars_str = " ".join(f"{k}={v}" for k, v in self._env_vars.items())
            full_cmd = f"cd {self._cwd} && {env_vars_str} {self._cmd}"
            exit_code, output = await self._sandbox.communicate(full_cmd)

            lines = output.splitlines()
            timestamp = int(time.time() * 1e9)  # nanoseconds
            for line in lines:
                message = ProcessMessage(line=line, timestamp=timestamp, error=False)
                self._output._add_stdout(message)
                if self._on_stdout:
                    self._on_stdout(message)

            self._output.exit_code = exit_code
            if self._on_exit:
                self._on_exit(exit_code)
        except Exception as e:
            logger.error(f"Error running process: {str(e)}")
            self._output.error = True
            if self._on_stderr:
                self._on_stderr(
                    ProcessMessage(
                        line=str(e), timestamp=int(time.time() * 1e9), error=True
                    )
                )
        finally:
            self._finished.set_result(True)

    async def wait(self, timeout: Optional[float] = None) -> ProcessOutput:
        try:
            await asyncio.wait_for(self._finished, timeout=timeout)
            return self._output
        except asyncio.TimeoutError:
            raise TimeoutException(f"Process did not finish within {timeout} seconds")

    async def send_stdin(self, data: str, timeout: Optional[float] = TIMEOUT) -> None:
        raise NotImplementedError(
            "send_stdin is not implemented for this Process class"
        )

    async def kill(self, timeout: Optional[float] = TIMEOUT) -> None:
        if self._task:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Failed to cancel process {self._process_id} within timeout"
                )
            except asyncio.CancelledError:
                pass


class ProcessManager:
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

        process_id = process_id or f"process_{int(time.time() * 1000)}"

        if not cwd and self._sandbox.cwd:
            cwd = self._sandbox.cwd

        process = Process(
            process_id=process_id,
            sandbox=self._sandbox,
            cmd=cmd,
            env_vars=env_vars,
            cwd=cwd,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
            on_exit=on_exit,
        )

        await process.start()
        logger.info(f"Started process (id: {process_id})")
        return process

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
        )
        return await process.wait(timeout)