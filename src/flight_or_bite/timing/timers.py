"""Wall-clock timing helpers (SPEC §6.2). Single clock everywhere: time.perf_counter_ns()."""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np


class Stopwatch:
    """Context manager measuring elapsed wall-clock nanoseconds."""

    def __init__(self) -> None:
        self.start_ns: int | None = None
        self.elapsed_ns: int | None = None

    def __enter__(self) -> Stopwatch:
        self.start_ns = time.perf_counter_ns()
        return self

    def __exit__(self, *exc: object) -> None:
        assert self.start_ns is not None
        self.elapsed_ns = time.perf_counter_ns() - self.start_ns


def busy_wait_ns(delay_ns: int) -> None:
    """Block for delay_ns by spinning on the clock.

    time.sleep() is not usable for known delays here: macOS coalesces timers of throttled
    processes, and sleep(10 ms) was observed to take up to 110 ms on the target machine.
    Spinning overshoots by microseconds at the cost of one busy core.
    """
    end = time.perf_counter_ns() + delay_ns
    while time.perf_counter_ns() < end:
        pass


@dataclass(frozen=True)
class LatencySummary:
    n: int
    p50_ms: float
    p90_ms: float
    p99_ms: float
    mean_ms: float  # supplementary only (SPEC §6.2)


def summarize_ns(samples_ns: Iterable[int]) -> LatencySummary:
    """p50/p90/p99 of latency samples given in nanoseconds."""
    arr = np.asarray(list(samples_ns), dtype=np.float64) / 1e6
    if arr.size == 0:
        raise ValueError("no latency samples")
    p50, p90, p99 = np.percentile(arr, [50, 90, 99])
    return LatencySummary(
        n=int(arr.size),
        p50_ms=float(p50),
        p90_ms=float(p90),
        p99_ms=float(p99),
        mean_ms=float(arr.mean()),
    )
