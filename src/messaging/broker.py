import asyncio
from dataclasses import dataclass, field

from src.messaging.topics import matches


@dataclass(eq=False)          # eq=False: compare by identity, so a Subscription can go in a set
class Subscription:
    patterns: tuple[str, ...]
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)


class Broker:
    """In-process publish/subscribe. One instance per process, created at startup
    and injected where needed (not a global Singleton)."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._subs: set[Subscription] = set()

    def subscribe(self, patterns) -> Subscription:
        sub = Subscription(tuple(patterns))
        self._subs.add(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        self._subs.discard(sub)

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)

    def publish(self, message: dict) -> None:
        # May be called from a worker thread (sync routes). asyncio queues are not
        # thread-safe, so ask the event loop to do the delivery on its own thread.
        self._loop.call_soon_threadsafe(self._fan_out, message)

    def _fan_out(self, message: dict) -> None:
        for sub in list(self._subs):
            if any(matches(p, message["topic"]) for p in sub.patterns):
                sub.queue.put_nowait(message)

    def close(self) -> None:
        """Wake every open stream with None so it can finish cleanly on shutdown."""
        for sub in list(self._subs):
            sub.queue.put_nowait(None)