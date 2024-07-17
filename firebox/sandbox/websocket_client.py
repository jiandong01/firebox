import asyncio
import logging
from queue import Queue
from threading import Event
from typing import Any, Callable, List, Optional

import websockets

logger = logging.getLogger(__name__)


class WebSocket:
    def __init__(
        self,
        url: str,
        started: Event,
        stopped: Event,
        queue_in: Queue[str],
        queue_out: Queue[str],
    ):
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self.url = url
        self.started = started
        self.stopped = stopped
        self._process_cleanup: List[Callable[[], Any]] = []
        self._queue_in = queue_in
        self._queue_out = queue_out

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(self.async_run())

    async def async_run(self):
        await self._connect()
        await self.close()

    async def _send_message(self):
        logger.debug("WebSocket starting to send messages")
        while True:
            if self._queue_in.empty():
                await asyncio.sleep(0)
                continue
            message = self._queue_in.get()
            logger.debug(f"WebSocket message to send: {message}")
            if self._ws:
                await self._ws.send(message)
                logger.debug(f"WebSocket message sent: {message}")
                self._queue_in.task_done()
            else:
                logger.error("No WebSocket connection")

    async def _receive_message(self):
        try:
            if not self._ws:
                logger.error("No WebSocket connection")
                return
            async for message in self._ws:
                logger.debug(f"WebSocket received message: {message}".strip())
                self._queue_out.put(message)
        except Exception as e:
            logger.error(f"WebSocket received error while receiving messages: {e}")

    async def _connect(self):
        logger.debug(f"WebSocket connecting to {self.url}")

        async for websocket in websockets.connect(self.url):
            try:
                self._ws = websocket
                self.started.set()
                logger.info(f"WebSocket connected to {self.url}")

                send_task = asyncio.create_task(
                    self._send_message(), name="send_message"
                )
                self._process_cleanup.append(send_task.cancel)

                receive_task = asyncio.create_task(
                    self._receive_message(), name="receive_message"
                )
                self._process_cleanup.append(receive_task.cancel)

                while not self.stopped.is_set():
                    await asyncio.sleep(0)

                logger.info("WebSocket stopped")
                break
            except websockets.ConnectionClosed:
                logger.warning("WebSocket disconnected, it will try to reconnect")
                if self.stopped.is_set():
                    break

    async def close(self):
        for cancel in self._process_cleanup:
            cancel()

        self._process_cleanup.clear()

        if self._ws:
            await self._ws.close()
