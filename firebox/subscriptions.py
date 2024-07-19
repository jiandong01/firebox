import asyncio
import os
import time
from typing import Callable, Any

from firebox.models import (
    FilesystemEvent,
    FilesystemOperation,
    ProcessEvent,
    ProcessEventType,
)
from firebox.logs import logger


class SubscriptionHandler:
    @staticmethod
    async def watch_directory(
        sandbox, path: str, handler: Callable[[FilesystemEvent], None]
    ):
        previous_state = set()

        async def poll_changes():
            nonlocal previous_state
            while True:
                try:
                    exit_code, output = await sandbox.communicate(f"ls -la {path}")
                    if exit_code == 0:
                        current_state = set(output.splitlines())
                        new_files = current_state - previous_state
                        removed_files = previous_state - current_state

                        for file_info in new_files.union(removed_files):
                            parts = file_info.split()
                            if len(parts) >= 9:
                                file_name = " ".join(parts[8:])
                                if file_name not in [
                                    ".",
                                    "..",
                                ]:  # Ignore . and .. entries
                                    is_dir = parts[0].startswith("d")
                                    operation = (
                                        FilesystemOperation.Create
                                        if file_info in new_files
                                        else FilesystemOperation.Remove
                                    )
                                    event = FilesystemEvent(
                                        path=os.path.join(path, file_name),
                                        name=file_name,
                                        operation=operation,
                                        timestamp=int(time.time() * 1e9),
                                        is_dir=is_dir,
                                    )
                                    handler(event)

                        previous_state = current_state

                    await asyncio.sleep(1)  # Poll every second
                except Exception as e:
                    logger.error(f"Error in file watcher: {str(e)}")
                    await asyncio.sleep(1)  # Wait before retrying

        task = asyncio.create_task(poll_changes())

        def unsubscribe():
            task.cancel()

        return unsubscribe

    @staticmethod
    async def watch_process(sandbox, pid: int, handler: Callable[[ProcessEvent], None]):
        async def poll_process():
            while True:
                try:
                    exit_code, output = await sandbox.communicate(
                        f"ps -p {pid} -o state="
                    )
                    if exit_code == 0:
                        if output.strip():
                            # Process is running, check for output
                            stdout, _ = await sandbox.communicate(
                                f"tail -n 1 /proc/{pid}/fd/1"
                            )
                            if stdout:
                                event = ProcessEvent(
                                    pid=pid,
                                    event_type=ProcessEventType.STDOUT,
                                    timestamp=int(time.time() * 1e9),
                                    data=stdout.strip(),
                                )
                                handler(event)

                            stderr, _ = await sandbox.communicate(
                                f"tail -n 1 /proc/{pid}/fd/2"
                            )
                            if stderr:
                                event = ProcessEvent(
                                    pid=pid,
                                    event_type=ProcessEventType.STDERR,
                                    timestamp=int(time.time() * 1e9),
                                    data=stderr.strip(),
                                )
                                handler(event)
                        else:
                            # Process has exited
                            exit_code, _ = await sandbox.communicate(f"echo $?")
                            event = ProcessEvent(
                                pid=pid,
                                event_type=ProcessEventType.EXIT,
                                timestamp=int(time.time() * 1e9),
                                exit_code=int(exit_code),
                            )
                            handler(event)
                            break
                    else:
                        # Process doesn't exist
                        event = ProcessEvent(
                            pid=pid,
                            event_type=ProcessEventType.EXIT,
                            timestamp=int(time.time() * 1e9),
                            exit_code=-1,
                        )
                        handler(event)
                        break

                    await asyncio.sleep(1)  # Poll every second
                except Exception as e:
                    logger.error(f"Error in process watcher: {str(e)}")
                    await asyncio.sleep(1)  # Wait before retrying

        task = asyncio.create_task(poll_process())

        def unsubscribe():
            task.cancel()

        return unsubscribe

    # Add other subscription methods here as needed
    # For example:
    # @staticmethod
    # async def watch_process(sandbox, pid: int, handler: Callable[[ProcessEvent], None]):
    #     ...
