"""WebSocket fan-out. Each client gets its own small queue + sender task, so one slow browser can
never delay the 500 ms broadcast to the others (NFR-SC3: 50+ concurrent clients)."""
from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

log = logging.getLogger("ws")


class Client:
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.queue: asyncio.Queue[tuple[str, bool]] = asyncio.Queue(maxsize=40)
        self.dropped = 0


class WSManager:
    def __init__(self) -> None:
        self.clients: set[Client] = set()
        self.peak = 0
        self.total_connections = 0

    @property
    def count(self) -> int:
        return len(self.clients)

    async def handle(self, ws: WebSocket, *initial: str) -> None:
        await ws.accept()
        client = Client(ws)
        self.clients.add(client)
        self.total_connections += 1
        self.peak = max(self.peak, len(self.clients))
        for text in initial:
            client.queue.put_nowait((text, True))
        sender = asyncio.create_task(self._sender(client))
        try:
            while True:                       # keep reading so disconnects are noticed (and pings answered)
                msg = await ws.receive_text()
                if msg == "ping":
                    client.queue.put_nowait(('{"type":"pong"}', True))
        except Exception:
            pass
        finally:
            sender.cancel()
            self.clients.discard(client)

    async def _sender(self, c: Client) -> None:
        try:
            while True:
                text, _important = await c.queue.get()
                await c.ws.send_text(text)
        except Exception:
            self.clients.discard(c)

    def broadcast(self, text: str, important: bool = False) -> None:
        for c in list(self.clients):
            if c.queue.full():
                # drop the oldest *snapshot*; alert events are kept whenever possible
                try:
                    old = c.queue.get_nowait()
                    c.dropped += 1
                    if old[1]:
                        c.queue.put_nowait(old)
                        continue
                except asyncio.QueueEmpty:
                    pass
            try:
                c.queue.put_nowait((text, important))
            except asyncio.QueueFull:
                c.dropped += 1
