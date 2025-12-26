"""Queue-based IPC for subprocess communication."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from multiprocessing import Queue
from queue import Empty
from typing import Any

from ..config.ipc import IPCConfig

logger = logging.getLogger("fastapi.ipc")


class IPCChannel:
    """
    Bidirectional queue-based IPC for subprocess communication.

    Provides async interface for request/response pattern used in FastAPI
    route handlers to communicate with the main process.

    Used inside the subprocess (FastAPI handlers) to:
    1. Submit requests to main process via request_q
    2. Wait for responses from main process via response_q
    3. Handle streaming responses (multiple chunks per request)

    Message Protocol:
    - Messages MUST have an `.id` attribute for routing
    - Streaming messages MUST have an `.is_final` attribute
    - Framework is agnostic about message types; users define their own
      Request/Response/StreamChunk dataclasses

    Example usage in FastAPI handler:
        async def inference(request: InferenceRequest, ipc: IPCChannel = Depends(get_ipc)):
            internal = InternalRequest(id=str(uuid4()), data=request.data)
            response = await ipc.submit(internal.id, internal, timeout=60.0)
            return response.result
    """

    def __init__(
        self,
        request_q: Queue[Any],
        response_q: Queue[Any],
        config: IPCConfig,
    ) -> None:
        """
        Initialize IPC channel.

        Args:
            request_q: Queue for sending requests to main process
            response_q: Queue for receiving responses from main process
            config: IPC configuration
        """
        self.request_q = request_q
        self.response_q = response_q
        self.config = config

        # Dual tracking: futures for blocking requests, async queues for streaming
        self.pending: dict[str, asyncio.Future[Any]] = {}
        self.pending_streams: dict[str, asyncio.Queue[Any]] = {}

        # Background polling task
        self._poll_task: asyncio.Task[None] | None = None

    @property
    def pending_count(self) -> int:
        """Number of requests awaiting response."""
        return len(self.pending) + len(self.pending_streams)

    @property
    def health_status(self) -> dict[str, Any]:
        """
        Health status for reporting.

        Returns dict with:
        - pending_requests: Current number of pending requests
        - max_pending: Configured maximum
        - is_healthy: True if under capacity
        """
        return {
            "pending_requests": self.pending_count,
            "max_pending": self.config.max_pending,
            "is_healthy": self.pending_count < self.config.max_pending,
        }

    async def submit(
        self,
        request_id: str,
        request: Any,
        timeout: float | None = None,
    ) -> Any:
        """
        Submit request and wait for response.

        Args:
            request_id: Unique identifier for this request (must match response.id)
            request: Request object to send to main process
            timeout: Override default response timeout (seconds)

        Returns:
            Response object from main process

        Raises:
            RuntimeError: If max_pending exceeded
            TimeoutError: If response not received within timeout
        """
        if self.pending_count >= self.config.max_pending:
            raise RuntimeError(
                f"Max pending requests exceeded ({self.config.max_pending})"
            )

        # Create future for response
        loop = asyncio.get_event_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self.pending[request_id] = future

        # Send request to main process
        self.request_q.put(request)

        # Wait for response with timeout
        effective_timeout = (
            timeout if timeout is not None else self.config.response_timeout
        )
        try:
            return await asyncio.wait_for(future, timeout=effective_timeout)
        except TimeoutError:
            # CRITICAL: Clean up on timeout to prevent memory leak
            self.pending.pop(request_id, None)
            raise TimeoutError(
                f"Request {request_id} timed out after {effective_timeout}s"
            )

    async def _yield_stream_chunks(
        self, request_id: str, chunk_queue: asyncio.Queue[Any]
    ) -> AsyncIterator[Any]:
        """Yield chunks from queue until final chunk received."""
        while True:
            try:
                chunk = await asyncio.wait_for(
                    chunk_queue.get(), timeout=self.config.response_timeout
                )
                yield chunk
                if getattr(chunk, "is_final", False):
                    break
            except TimeoutError:
                logger.warning(f"Streaming request {request_id} timed out")
                raise TimeoutError(
                    f"Streaming request {request_id} timed out waiting for chunk"
                )

    async def submit_streaming(
        self, request_id: str, request: Any
    ) -> AsyncIterator[Any]:
        """
        Submit streaming request and yield response chunks.

        Yields chunks until one with is_final=True is received.

        Raises:
            RuntimeError: If max_pending exceeded
            TimeoutError: If a chunk is not received within timeout
        """
        if self.pending_count >= self.config.max_pending:
            raise RuntimeError(
                f"Max pending requests exceeded ({self.config.max_pending})"
            )

        chunk_queue: asyncio.Queue[Any] = asyncio.Queue()
        self.pending_streams[request_id] = chunk_queue
        self.request_q.put(request)

        try:
            async for chunk in self._yield_stream_chunks(request_id, chunk_queue):
                yield chunk
        finally:
            self.pending_streams.pop(request_id, None)

    async def start_polling(self) -> None:
        """
        Start background task to poll response queue.

        Must be called during FastAPI startup event.
        """
        if self._poll_task is not None:
            return
        self._poll_task = asyncio.create_task(self._poll_responses())
        logger.info("started IPC response polling task")

    async def stop_polling(self) -> None:
        """
        Stop polling and cancel pending requests.

        Must be called during FastAPI shutdown event.
        """
        if self._poll_task is None:
            return

        self._poll_task.cancel()
        try:
            await self._poll_task
        except asyncio.CancelledError:
            pass
        self._poll_task = None

        # Cancel all pending futures
        for request_id, future in list(self.pending.items()):
            if not future.done():
                future.cancel()
        self.pending.clear()

        # Signal end to all pending streams
        for request_id, queue in list(self.pending_streams.items()):
            # Put a sentinel to unblock any waiting consumers
            # They should check is_final or handle the cancellation
            await queue.put(None)
        self.pending_streams.clear()

        logger.info("stopped IPC response polling task")

    async def _read_queue_item(self, loop: asyncio.AbstractEventLoop) -> Any | None:
        """Read item from response queue without blocking event loop."""
        try:
            return await loop.run_in_executor(
                None, lambda: self.response_q.get(timeout=self.config.poll_interval)
            )
        except Empty:
            await asyncio.sleep(0)
            return None

    async def _dispatch_response(self, item: Any) -> None:
        """Route response to appropriate handler based on request_id."""
        req_id = getattr(item, "id", None)
        if req_id is None:
            logger.warning(f"Received response without id attribute: {type(item)}")
        elif req_id in self.pending_streams:
            await self._handle_stream_chunk(req_id, item)
        elif req_id in self.pending:
            self._handle_response(req_id, item)
        else:
            logger.warning(f"Received response for unknown request: {req_id}")

    async def _poll_responses(self) -> None:
        """Background task polling response queue and resolving futures."""
        loop = asyncio.get_event_loop()

        while True:
            try:
                item = await self._read_queue_item(loop)
                if item is not None:
                    await self._dispatch_response(item)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("error polling responses", extra={"exception": e})
                await asyncio.sleep(self.config.poll_interval)

    async def _handle_stream_chunk(self, request_id: str, chunk: Any) -> None:
        """Handle streaming response chunk."""
        queue = self.pending_streams.get(request_id)
        if queue is not None:
            await queue.put(chunk)
        else:
            logger.warning(f"Received chunk for unknown stream: {request_id}")

    def _handle_response(self, request_id: str, response: Any) -> None:
        """Handle single response (non-streaming)."""
        future = self.pending.pop(request_id, None)
        if future is not None and not future.done():
            # Check for error in response
            error = getattr(response, "error", None)
            if error:
                future.set_exception(RuntimeError(error))
            else:
                future.set_result(response)
        elif future is None:
            logger.warning(f"Received response for unknown request: {request_id}")
