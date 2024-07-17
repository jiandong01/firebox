import json
import logging
import threading
import time

from concurrent.futures import TimeoutError
from queue import Queue
from threading import Event
from typing import Any, Callable, Dict, Iterator, List, Union, Optional
from jsonrpcclient import Error, Ok, request_json
from jsonrpcclient.id_generators import decimal as decimal_id_generator
from jsonrpcclient.responses import Response
from pydantic import BaseModel, Field

from firebox.constants import TIMEOUT
from firebox.sandbox.exception import RpcException, TimeoutException, SandboxException
from firebox.sandbox.websocket_client import WebSocket
from firebox.utils.future import DeferredFuture

logger = logging.getLogger(__name__)


class Notification(BaseModel):
    """Notification."""

    method: str
    params: Dict


Message = Union[Response, Notification]


def to_response_or_notification(response: Dict[str, Any]) -> Message:
    """Create a Response namedtuple from a dict."""
    if "error" in response:
        return Error(
            response["error"]["code"],
            response["error"]["message"],
            response["error"].get("data"),
            response["id"],
        )
    elif "result" in response and "id" in response:
        return Ok(response["result"], response["id"])
    elif "params" in response:
        return Notification(method=response["method"], params=response["params"])

    raise ValueError("Invalid response", response)


class SandboxRpc(BaseModel):
    url: str
    on_message: Callable[[Notification], None]

    id_generator: Iterator[int] = Field(default_factory=decimal_id_generator)
    waiting_for_replies: Dict[int, DeferredFuture] = Field(default_factory=dict)
    queue_in: Queue = Field(default_factory=Queue)
    queue_out: Queue = Field(default_factory=Queue)
    process_cleanup: List[Callable[[], Any]] = Field(default_factory=list)
    websocket_task: Optional[threading.Thread] = None
    closed: bool = False

    class Config:
        arbitrary_types_allowed = True

    def process_messages(self):
        while True:
            data = self.queue_out.get()
            logger.debug(f"WebSocket received message: {data}".strip())
            self._receive_message(data)
            self.queue_out.task_done()

    def connect(self, timeout: float = TIMEOUT):
        started = Event()
        stopped = Event()
        self.process_cleanup.append(stopped.set)

        threading.Thread(
            target=self.process_messages, daemon=True, name="firebox-process-messages"
        ).start()

        threading.Thread(
            target=WebSocket(
                url=self.url,
                queue_in=self.queue_in,
                queue_out=self.queue_out,
                started=started,
                stopped=stopped,
            ).run,
            daemon=True,
            name="firebox-websocket",
        ).start()

        logger.info("WebSocket waiting to start")

        try:
            start_time = time.time()
            while (
                not started.is_set()
                and time.time() - start_time < timeout
                and not self.closed
            ):
                time.sleep(0.1)

            if not started.is_set():
                logger.error("WebSocket failed to start")
                raise TimeoutException("WebSocket failed to start")
        except BaseException as e:
            self.close()
            raise SandboxException(f"WebSocket failed to start: {e}") from e

        logger.info("WebSocket started")

    def send_message(
        self,
        method: str,
        params: List[Any],
        timeout: Optional[float],
    ) -> Any:
        timeout = timeout or TIMEOUT

        id = next(self.id_generator)
        request = request_json(method, params, id)
        future_reply = DeferredFuture(self.process_cleanup)

        try:
            self.waiting_for_replies[id] = future_reply
            logger.debug(f"WebSocket queueing message: {request}")
            self.queue_in.put(request)
            logger.debug(f"WebSocket waiting for reply: {request}")
            try:
                r = future_reply.result(timeout=timeout)
            except TimeoutError as e:
                logger.error(f"WebSocket timed out while waiting for: {request} {e}")
                raise TimeoutException(
                    f"WebSocket timed out while waiting for: {request} {e}"
                ) from e
            return r
        except Exception as e:
            logger.error(f"WebSocket received error while waiting for: {request} {e}")
            raise e
        finally:
            del self.waiting_for_replies[id]
            logger.debug(f"WebSocket removed waiting handler for {id}")

    def _receive_message(self, data: str):
        logger.debug(f"Processing message: {data}".strip())

        message = to_response_or_notification(json.loads(data))

        logger.debug(
            f"Current waiting handlers: {list(self.waiting_for_replies.keys())}"
        )
        if isinstance(message, Ok):
            if (
                message.id in self.waiting_for_replies
                and self.waiting_for_replies[message.id]
            ):
                self.waiting_for_replies[message.id](message.result)
                return
        elif isinstance(message, Error):
            if (
                message.id in self.waiting_for_replies
                and self.waiting_for_replies[message.id]
            ):
                self.waiting_for_replies[message.id].reject(
                    RpcException(
                        code=message.code,
                        message=message.message,
                        id=message.id,
                        data=message.data,
                    )
                )
                return
        elif isinstance(message, Notification):
            self.on_message(message)

    def close(self):
        self.closed = True

        for cancel in self.process_cleanup:
            cancel()

        self.process_cleanup.clear()

        # .copy() prevents a RuntimeError: dictionary changed size during iteration
        for handler in self.waiting_for_replies.copy().values():
            handler.cancel()
            del handler
