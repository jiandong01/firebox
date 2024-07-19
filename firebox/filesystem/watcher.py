import asyncio
import logging
from typing import Any, Callable, Optional, Set

from pydantic import BaseModel

from firebox.constants import TIMEOUT
from firebox.exception import FilesystemException
from firebox.utils.str import snake_case_to_camel_case
from firebox.models import FileSystemOperation

logger = logging.getLogger(__name__)


class FilesystemEvent(BaseModel):
    path: str
    name: str
    operation: FileSystemOperation
    timestamp: int
    """
    Unix epoch in nanoseconds
    """
    is_dir: bool

    class ConfigDict:
        alias_generator = snake_case_to_camel_case


class Watcher:
    @property
    def path(self) -> str:
        """
        The path being watched.
        """
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
        """
        Start the filesystem watcher.

        :param timeout: Specify the duration, in seconds to give the method to finish its execution before it times out.
        """
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
        """
        Stop the filesystem watcher.
        """
        logger.debug(f"Stopping filesystem watcher for {self.path}")

        self._listeners.clear()
        if self._unsubscribe:
            try:
                await self._unsubscribe()
                self._unsubscribe = None
                logger.debug(f"Stopped filesystem watcher for {self.path}")
            except Exception as e:
                raise FilesystemException(
                    f"Failed to stop watcher for {self.path}: {str(e)}"
                ) from e

    def add_event_listener(
        self, listener: Callable[[FilesystemEvent], Any]
    ) -> Callable[[], None]:
        """
        Add a listener for filesystem events.

        :param listener: Listener to add
        :return: Function that removes the listener
        """
        logger.debug(f"Adding filesystem watcher listener for {self.path}")

        self._listeners.add(listener)

        def remove_listener() -> None:
            self._listeners.remove(listener)

        return remove_listener

    def _handle_filesystem_events(self, event: dict) -> None:
        try:
            filesystem_event = FilesystemEvent(**event)
            for listener in self._listeners:
                asyncio.create_task(self._call_listener(listener, filesystem_event))
        except Exception as e:
            logger.error(f"Error handling filesystem event: {str(e)}")

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

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.stop()
