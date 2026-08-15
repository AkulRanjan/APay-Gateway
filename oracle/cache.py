from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass
class _Entry(Generic[T]):
    value: T
    stored_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._values: dict[str, _Entry[T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._values.get(key)
        if entry is None or time.monotonic() - entry.stored_at > self.ttl_seconds:
            self._values.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: T) -> None:
        self._values[key] = _Entry(value=value, stored_at=time.monotonic())
