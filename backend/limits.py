"""Eşzamanlılık ve hız sınırları. Kuyruk yok: yer yoksa istek anında reddedilir.

Tek event loop'ta çalıştığı için sayaçlara kilit gerekmiyor; aralarında
await olmayan kontrol + artırma atomiktir.
"""

from __future__ import annotations

import time
from collections import Counter, deque


class Slots:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.used = 0

    def try_acquire(self) -> bool:
        if self.used >= self.capacity:
            return False
        self.used += 1
        return True

    def release(self) -> None:
        self.used = max(0, self.used - 1)


class PerKeySlots:
    """Anahtar (IP) başına eşzamanlı iş sınırı. capacity <= 0 ise sınırsız."""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._counts: Counter[str] = Counter()

    def try_acquire(self, key: str) -> bool:
        if self.capacity > 0 and self._counts[key] >= self.capacity:
            return False
        self._counts[key] += 1
        return True

    def release(self, key: str) -> None:
        self._counts[key] -= 1
        if self._counts[key] <= 0:
            del self._counts[key]


class RateLimiter:
    """Kayan pencere: anahtar başına son `window` saniyede en fazla `limit` olay.
    limit <= 0 ise sınırsız. Boşalan anahtarlar silinir, bellek büyümez."""

    def __init__(self, limit: int, window: float = 60.0):
        self.limit = limit
        self.window = window
        self._events: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        events = self._events.setdefault(key, deque())
        while events and now - events[0] > self.window:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        self._prune(now)
        return True

    def _prune(self, now: float) -> None:
        if len(self._events) < 1024:
            return
        for key in [k for k, v in self._events.items() if not v or now - v[-1] > self.window]:
            del self._events[key]
