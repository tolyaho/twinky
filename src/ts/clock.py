"""Time.

Nothing in a query path may call time.time() directly. Replay must be bit-reproducible,
and every window in the legacy code was anchored to wall-clock `now_ms()`, which returns
nothing at all when the input is a recording from yesterday.
"""
from __future__ import annotations

import time
from typing import Iterable, Protocol


class Clock(Protocol):
    def now_ms(self) -> int: ...


class WallClock:
    """Live mode only."""

    def now_ms(self) -> int:
        return int(time.time() * 1000)


class FixtureClock:
    """Replay mode. Virtual time stepped explicitly along fixture timestamps.

    >>> c = FixtureClock(start_ms=1000)
    >>> c.now_ms()
    1000
    >>> c.advance_to(5000); c.now_ms()
    5000
    """

    def __init__(self, start_ms: int) -> None:
        self._now = int(start_ms)

    def now_ms(self) -> int:
        return self._now

    def advance_to(self, ts_ms: int) -> None:
        ts_ms = int(ts_ms)
        if ts_ms < self._now:
            raise ValueError(f"clock cannot move backwards: {self._now} -> {ts_ms}")
        self._now = ts_ms

    def advance_by(self, delta_ms: int) -> None:
        self.advance_to(self._now + int(delta_ms))

    def ticks(self, end_ms: int, step_ms: int) -> Iterable[int]:
        """Deterministic tick sequence. Replaces every `await asyncio.sleep(N)` loop."""
        t = self._now
        while t <= end_ms:
            self.advance_to(t)
            yield t
            t += step_ms


def minutes_ms(m: float) -> int:
    return round(m * 60_000)


def seconds_ms(s: float) -> int:
    return round(s * 1000)
