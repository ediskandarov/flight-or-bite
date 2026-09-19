"""LIF backend benchmark (SPEC §9 `fob perf`, §6.2): wall time, RTF, early stopping, load time."""

from __future__ import annotations

import subprocess
import time
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from flight_or_bite.lif.backend import LIFBackend, Stimulus, StopOnFirstSpike, TrialResult


@dataclass
class BackendPerf:
    backend: str
    t_load_s: float
    n_full: int
    full_wall_s_p50: float
    full_wall_s_max: float
    rtf_p50: float
    spikes_per_trial: float
    mn9_rate_hz: float
    n_stop: int
    stop_fraction: float  # trials in which the watched neuron fired at all
    stop_t_sim_ms_p50: float
    stop_wall_s_p50: float
    first_trial_wall_s: float  # includes one-off costs (code generation, caches)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def throttle_check(n: int = 15) -> dict[str, Any]:
    """Signs that this process is being throttled (decision D5): sleep overshoot, power source."""
    over = []
    for _ in range(n):
        t0 = time.perf_counter_ns()
        time.sleep(0.010)
        over.append((time.perf_counter_ns() - t0) / 1e6 - 10.0)
    try:
        batt = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5)
        power = batt.stdout.splitlines()[0].strip() if batt.stdout else "unknown"
    except (OSError, subprocess.SubprocessError):
        power = "unknown"
    median = float(np.median(over))
    return {
        "sleep_10ms_overshoot_ms_median": round(median, 2),
        "sleep_10ms_overshoot_ms_max": round(float(np.max(over)), 2),
        "timer_throttled": median > 5.0,
        "power": power,
    }


def bench_backend(
    backend: LIFBackend,
    stimulus: Stimulus,
    watch: int,
    *,
    t_ms: float,
    n_full: int,
    n_stop: int,
    seed_base: int,
) -> tuple[BackendPerf, list[TrialResult]]:
    """One process, graph already in memory; t_wall covers input generation and simulation."""
    first = backend.run_trial(stimulus, t_ms, seed=seed_base - 1)  # warm-up, reported separately
    full = [backend.run_trial(stimulus, t_ms, seed=seed_base + k) for k in range(n_full)]
    stop = StopOnFirstSpike(np.array([watch]))
    stopped = [
        backend.run_trial(stimulus, t_ms, seed=seed_base + k, stop=stop) for k in range(n_stop)
    ]
    wall = np.array([r.t_wall_ns for r in full]) / 1e9
    perf = BackendPerf(
        backend=backend.name,
        t_load_s=backend.t_load_s,
        n_full=n_full,
        full_wall_s_p50=float(np.median(wall)),
        full_wall_s_max=float(wall.max()),
        rtf_p50=float(np.median([r.rtf for r in full])),
        spikes_per_trial=float(np.mean([r.spike_i.size for r in full])),
        mn9_rate_hz=float(np.mean([r.rate_hz(watch) for r in full])),
        n_stop=n_stop,
        stop_fraction=float(np.mean([r.stopped_early for r in stopped])),
        stop_t_sim_ms_p50=float(np.median([r.t_sim_ms for r in stopped])),
        stop_wall_s_p50=float(np.median([r.t_wall_ns for r in stopped]) / 1e9),
        first_trial_wall_s=first.t_wall_ns / 1e9,
    )
    return perf, full


def spike_pairs(result: TrialResult, dt_ms: float) -> set[tuple[int, int]]:
    steps = np.rint(result.spike_t_ms / dt_ms).astype(np.int64)
    return set(zip(result.spike_i.tolist(), steps.tolist(), strict=True))
