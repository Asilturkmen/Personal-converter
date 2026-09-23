"""Eşzamanlılık sınırları. Kuyruk yok: yer yoksa istek anında reddedilir.

Tek event loop'ta çalıştığı için sayaçlara kilit gerekmiyor; aralarında
await olmayan kontrol + artırma atomiktir.
"""

from __future__ import annotations

from collections import Counter


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
    """IP başına eşzamanlı iş sınırı. capacity <= 0 ise sınırsız."""

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
