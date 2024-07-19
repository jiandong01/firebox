import asyncio
import time
from typing import Dict, Optional, Any, List, Callable
from ..logs import setup_logging
from ..exceptions import TimeoutError
from ..models import EnvVars, ProcessMessage

logger = setup_logging()


class ProcessManager:
    def __init__(self, sandbox):
        self.sandbox = sandbox

    async def start(
        self,
        cmd: str,
        env_vars: Optional[EnvVars] = None,
        cwd: Optional[str] = None,
        timeout: int = 60,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Callable[[int], Any]] = None,
    ) -> "RunningProcess":
        logger.info(f"Starting process: {cmd}")
        full_cmd = []

        if env_vars:
            env_vars_str = " ".join(f"{k}={v}" for k, v in env_vars.items())
            full_cmd.append(f"export {env_vars_str} &&")

        if cwd:
            full_cmd.append(f"cd {cwd} &&")

        full_cmd.append(cmd)
        full_cmd_str = " ".join(full_cmd)

        process_id = f"process_{int(time.time() * 1000)}"
        output_file = f"/tmp/{process_id}_output"
        exit_code_file = f"/tmp/{process_id}_exit_code"

        bg_cmd = f"""
        (
            {full_cmd_str}
            echo $? > {exit_code_file}
        ) > {output_file} 2>&1 & echo $!
        """

        logger.debug(f"Full background command: {bg_cmd}")

        try:
            pid_output, _ = await self.sandbox.communicate(bg_cmd, timeout=timeout)
            logger.info(f"Process start output: {pid_output}")
            pid = int(pid_output.strip())
            logger.info(f"Process started with PID: {pid}")

            running_process = RunningProcess(
                self,
                pid,
                process_id,
                output_file,
                exit_code_file,
                on_stdout=on_stdout,
                on_stderr=on_stderr,
                on_exit=on_exit,
            )

            if on_stdout or on_stderr:
                asyncio.create_task(running_process._stream_output())

            await asyncio.sleep(0.1)
            logger.debug(f"Process {pid} initialization complete")

            return running_process
        except ValueError:
            logger.error(f"Failed to start process. Output: {pid_output}")
            raise RuntimeError(f"Failed to start process. Output: {pid_output}")
        except Exception as e:
            logger.error(f"Error starting process: {str(e)}")
            raise

    async def list(self) -> List[Dict[str, Any]]:
        logger.info("Listing all processes in the sandbox")
        cmd = "ps -eo pid,ppid,cmd --no-headers"
        output, _ = await self.sandbox.communicate(cmd)
        processes = []
        for line in output.strip().split("\n"):
            pid, ppid, *cmd_parts = line.split()
            processes.append(
                {"pid": int(pid), "ppid": int(ppid), "command": " ".join(cmd_parts)}
            )
        return processes

    async def get(self, pid: int) -> Optional["RunningProcess"]:
        if await self._is_process_running(pid):
            return RunningProcess(
                self,
                pid,
                f"process_{pid}",
                f"/tmp/process_{pid}_output",
                f"/tmp/process_{pid}_exit_code",
            )
        return None

    async def _is_process_running(self, pid: int) -> bool:
        cmd = f"ps -o pid=,stat= -p {pid}"
        result, _ = await self.sandbox.communicate(cmd)
        is_running = bool(result.strip())
        status = result.split()[-1] if result.strip() else "N/A"
        logger.info(f"Process {pid} status: {status}, running: {is_running}")
        return is_running


class RunningProcess:
    def __init__(
        self,
        process_manager: ProcessManager,
        pid: int,
        process_id: str,
        output_file: str,
        exit_code_file: str,
        on_stdout: Optional[Callable[[ProcessMessage], Any]] = None,
        on_stderr: Optional[Callable[[ProcessMessage], Any]] = None,
        on_exit: Optional[Callable[[int], Any]] = None,
    ):
        self.process_manager = process_manager
        self.pid = pid
        self.process_id = process_id
        self.output_file = output_file
        self.exit_code_file = exit_code_file
        self.on_stdout = on_stdout
        self.on_stderr = on_stderr
        self.on_exit = on_exit
        self.output = {"stdout": "", "stderr": ""}
        logger.debug(f"RunningProcess initialized for PID: {pid}")

    async def wait(self, timeout: Optional[int] = None) -> Dict[str, Any]:
        logger.info(f"Waiting for process {self.pid} to complete")
        start_time = time.time()

        while True:
            if await self._is_process_complete():
                logger.debug(f"Process {self.pid} completed")
                break
            if timeout and (time.time() - start_time) > timeout:
                logger.warning(f"Process {self.pid} timed out after {timeout} seconds")
                raise TimeoutError(
                    f"Process {self.pid} did not complete within the specified timeout."
                )
            await asyncio.sleep(0.1)

        result = await self.get_result()
        if self.on_exit:
            logger.debug(f"Calling on_exit callback for process {self.pid}")
            self.on_exit(result["exit_code"])
        return result

    async def kill(self):
        logger.info(f"Attempting to kill process {self.pid}")

        # Try SIGTERM first
        await self.process.sandbox.communicate(f"kill -TERM {self.pid}")
        logger.info(f"Sent SIGTERM to process {self.pid}")

        # Wait for up to 5 seconds for the process to terminate or become a zombie
        for i in range(50):
            status = await self._get_process_status()
            if status == "" or status == "Z":
                logger.info(
                    f"Process {self.pid} terminated or became a zombie after SIGTERM"
                )
                break
            await asyncio.sleep(0.1)
            if i % 10 == 0:  # Log every second
                logger.info(
                    f"Waiting for process {self.pid} to terminate after SIGTERM... ({i/10}s)"
                )

        # If the process is still running (not a zombie), try SIGKILL
        if status not in ["", "Z"]:
            logger.warning(
                f"Process {self.pid} did not respond to SIGTERM, sending SIGKILL"
            )
            await self.process.sandbox.communicate(f"kill -KILL {self.pid}")

            # Wait again for up to 5 seconds
            for i in range(50):
                status = await self._get_process_status()
                if status == "" or status == "Z":
                    logger.info(
                        f"Process {self.pid} terminated or became a zombie after SIGKILL"
                    )
                    break
                await asyncio.sleep(0.1)
                if i % 10 == 0:
                    logger.info(
                        f"Waiting for process {self.pid} to terminate after SIGKILL... ({i/10}s)"
                    )

        # If the process is a zombie, try to reap it
        if status == "Z":
            logger.info(f"Attempting to reap zombie process {self.pid}")
            await self.process.sandbox.communicate(f"wait {self.pid}")

        # Final check
        final_status = await self._get_process_status()
        if final_status == "":
            logger.info(f"Process {self.pid} successfully terminated and reaped")
        else:
            logger.warning(
                f"Process {self.pid} final status: '{final_status}'. It may need manual cleanup."
            )

        # We consider the kill successful even if the process is a zombie,
        # as it's no longer running and will be cleaned up by the system
        return

    async def send_stdin(self, input: str):
        logger.info(f"Sending stdin to process {self.pid}")
        await self.process_manager.sandbox.communicate(
            f"echo '{input}' >> {self.output_file}"
        )
        logger.debug(f"Stdin sent to process {self.pid}: {input}")

    async def is_running(self) -> bool:
        status = await self._get_process_status()
        is_running = status != "" and status != "Z"
        logger.info(
            f"Process {self.pid} running status: {is_running} (status: '{status}')"
        )
        return is_running

    async def get_result(self) -> Dict[str, Any]:
        logger.info(f"Getting result for process {self.pid}")
        while not await self._is_process_complete():
            await asyncio.sleep(0.1)

        output, _ = await self.process_manager.sandbox.communicate(
            f"cat {self.output_file}"
        )
        exit_code_str, _ = await self.process_manager.sandbox.communicate(
            f"cat {self.exit_code_file}"
        )

        logger.info(
            f"Process {self.pid} result. Output: {output}, Exit code string: {exit_code_str}"
        )

        try:
            exit_code = int(exit_code_str.strip())
        except ValueError:
            logger.warning(f"Could not parse exit code for process {self.pid}")
            exit_code = None

        self.output["stdout"] = output.strip()
        return {"stdout": output.strip(), "exit_code": exit_code}

    async def _get_process_status(self) -> str:
        cmd = f"ps -o stat= -p {self.pid}"
        result, _ = await self.process_manager.sandbox.communicate(cmd)
        status = result.strip()
        logger.info(f"Process {self.pid} status: '{status}'")
        return status

    async def _is_process_complete(self) -> bool:
        cmd = f"[ -f {self.exit_code_file} ] && echo 'complete' || echo 'incomplete'"
        result, _ = await self.process_manager.sandbox.communicate(cmd)
        result = result.strip()
        logger.info(f"Process {self.pid} result: '{result}'")
        is_complete = result == "complete"
        logger.info(f"Process {self.pid} completion status: {is_complete}")
        return is_complete

    async def _stream_output(self):
        logger.debug(f"Starting output streaming for process {self.pid}")
        last_size = 0
        completion_time = None
        while True:
            current_size, _ = await self.process_manager.sandbox.communicate(
                f"wc -c < {self.output_file}"
            )
            current_size = int(current_size)
            if current_size > last_size:
                new_output, _ = await self.process_manager.sandbox.communicate(
                    f"tail -c +{last_size + 1} {self.output_file}"
                )
                logger.debug(f"New output for process {self.pid}: {new_output}")
                if self.on_stdout or self.on_stderr:
                    timestamp = int(time.time_ns())
                    message = ProcessMessage(line=new_output, timestamp=timestamp)
                    if self.on_stdout:
                        self.on_stdout(message)
                    if self.on_stderr:
                        message.error = True
                        self.on_stderr(message)
                last_size = current_size

            if await self._is_process_complete():
                if completion_time is None:
                    completion_time = time.time()
                elif (
                    time.time() - completion_time > 1
                ):  # Continue streaming for 1 second after completion
                    break

            await asyncio.sleep(0.1)

        logger.debug(f"Output streaming completed for process {self.pid}")
