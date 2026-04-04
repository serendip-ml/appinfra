"""Bidirectional channel abstraction for service communication.

Provides both sync and async APIs for request/response patterns between
services and their runners, or between parent and child processes.

Architecture:
- Transport / AsyncTransport: Wire-level protocol (implement for custom transports)
- Channel / AsyncChannel: Concrete channel with correlation logic (wraps a Transport)
- QueueChannelFactory / ProcessQueueChannelFactory: Create Channel pairs with built-in transports

Custom transport example:
    from appinfra.service import Channel, ChannelTimeoutError, Transport

    class ZMQTransport:
        def send(self, message): ...
        def recv(self, timeout=None): ...
        def close(self): ...
        @property
        def is_closed(self) -> bool: ...

    channel = Channel(ZMQTransport(socket))

Built-in usage via factory:
    from appinfra.service import QueueChannelFactory

    factory = QueueChannelFactory()
    pair = factory.create_pair()
    pair.parent.send(Message(payload="hello"))
"""

from .async_ import (
    AsyncChannel,
    AsyncProcessQueueTransport,
    AsyncQueueTransport,
    AsyncTransport,
)
from .base import HasId, Message
from .sync import Channel, ProcessQueueTransport, QueueTransport, Transport

__all__ = [
    # Base types
    "Message",
    "HasId",
    # Sync
    "Transport",
    "Channel",
    "QueueTransport",
    "ProcessQueueTransport",
    # Async
    "AsyncTransport",
    "AsyncChannel",
    "AsyncQueueTransport",
    "AsyncProcessQueueTransport",
]
