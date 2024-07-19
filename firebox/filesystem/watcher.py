import asyncio
from typing import Callable, Any, Optional, Set

from firebox.constants import TIMEOUT
from firebox.exception import FilesystemException
from firebox.models import FilesystemEvent, FilesystemOperation
from firebox.logs import logger


class Watcher:
    @property
    def path(self) -> str:
        return self._path

    def __init__(
        self,
        connection,
        path: str,
        service_name: str,
    ):
        self._connection = connection
        self._path = path
        self._service_name = service_name
        self._unsubscribe: Optional[Callable[[], Any]] = None
        self._listeners: Set[Callable[[FilesystemEvent], Any]] = set()

    async def start(self, timeout: Optional[float] = TIMEOUT) -> None:
        if self._unsubscribe:
            return

        logger.debug(f"Starting filesystem watcher for {self.path}")
        try:
            self._unsubscribe = await self._connection._subscribe(
                self._service_name,
                self._handle_filesystem_events,
                "watchDir",
                self.path,
                timeout=timeout,
            )
            logger.debug(f"Started filesystem watcher for {self.path}")
        except Exception as e:
            raise FilesystemException(
                f"Failed to start watcher for {self.path}: {str(e)}"
            ) from e

    async def stop(self) -> None:
        logger.debug(f"Stopping filesystem watcher for {self.path}")

        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
            logger.debug(f"Stopped filesystem watcher for {self.path}")

        self._listeners.clear()

    def add_event_listener(
        self, listener: Callable[[FilesystemEvent], Any]
    ) -> Callable[[], None]:
        self._listeners.add(listener)
        return lambda: self._listeners.remove(listener)

    def _handle_filesystem_events(self, event: FilesystemEvent) -> None:
        for listener in self._listeners:
            asyncio.create_task(self._call_listener(listener, event))

    async def _call_listener(
        self, listener: Callable[[FilesystemEvent], Any], event: FilesystemEvent
    ) -> None:
        try:
            if asyncio.iscoroutinefunction(listener):
                await listener(event)
            else:
                listener(event)
        except Exception as e:
            logger.error(f"Error in filesystem event listener: {str(e)}")
