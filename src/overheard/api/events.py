"""Server-sent events (`GET /api/events`): what happens while the console is open, pushed to every browser.

  alert   a code-word trigger fired: an alerted voicemail reached the desk
  ticket  a ticket was created, or its decision was read back (from the mock board or hearthboard)

The bus is in-process: routes run in worker threads and publish from there; each open stream has a queue on the
event loop, filled thread-safely."""

from __future__ import annotations

import asyncio
import json
import threading


class Bus:
    def __init__(self) -> None:
        self._subs: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subs.append((asyncio.get_running_loop(), q))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs = [(lp, x) for lp, x in self._subs if x is not q]

    def publish(self, kind: str, data: dict) -> None:
        """From any thread. A browser that has fallen 200 events behind misses the rest (it refetches anyway)."""
        with self._lock:
            subs = list(self._subs)
        for loop, q in subs:
            def put(q=q):
                if not q.full():
                    q.put_nowait((kind, data))
            try:
                loop.call_soon_threadsafe(put)
            except RuntimeError:        # that stream's loop is gone
                self.unsubscribe(q)

    @property
    def listeners(self) -> int:
        return len(self._subs)


def frame(kind: str, data: dict) -> str:
    return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
