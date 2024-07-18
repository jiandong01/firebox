import asyncio
from typing import Callable, List, Union, Coroutine
import inspect
from firebox.exceptions import FilesystemError
from firebox.logs import logger


class Watcher:
    def __init__(self, filesystem, path: str):
        self.filesystem = filesystem
        self.path = path
        self.listeners: List[Union[Callable, Callable[..., Coroutine]]] = []
        self._task = None

    def add_event_listener(self, callback: Union[Callable, Callable[..., Coroutine]]):
        self.listeners.append(callback)

    async def _watch(self):
        initial_files = set(await self.filesystem.list(self.path))
        while True:
            await asyncio.sleep(1)
            try:
                current_files = set(await self.filesystem.list(self.path))

                # Check for new files
                for file in current_files - initial_files:
                    await self._notify_listeners("created", f"{self.path}/{file}")

                # Check for deleted files
                for file in initial_files - current_files:
                    await self._notify_listeners("deleted", f"{self.path}/{file}")

                initial_files = current_files
            except Exception as e:
                logger.error(f"Error while watching directory: {str(e)}")
                raise FilesystemError(f"Error while watching directory: {str(e)}")

    async def _notify_listeners(self, event_type: str, file_path: str):
        event = {"type": event_type, "path": file_path}
        for listener in self.listeners:
            if inspect.iscoroutinefunction(listener):
                await listener(event)
            else:
                listener(event)

    def start(self):
        if not self._task:
            self._task = asyncio.create_task(self._watch())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
