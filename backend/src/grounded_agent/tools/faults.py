"""Deliberate upstream faults for get_account_state (data/tools.md: ~1 call in 12 times out).

Seedable for reproducible evals; `force_timeout()` lets a single request (demo or eval case)
force the failure without affecting concurrent requests.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_forced_timeout: ContextVar[bool] = ContextVar("forced_timeout", default=False)


@contextmanager
def force_timeout() -> Iterator[None]:
    token = _forced_timeout.set(True)
    try:
        yield
    finally:
        _forced_timeout.reset(token)


class FaultInjector:
    def __init__(self, timeout_rate: float, seed: int | None = None) -> None:
        self._rate = timeout_rate
        self._rng = random.Random(seed)

    def should_timeout(self) -> bool:
        if _forced_timeout.get():
            return True
        return self._rng.random() < self._rate
