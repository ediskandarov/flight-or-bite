"""Motor decoding (SPEC §4.1, decision D25).

EAT     the sliding-window MN9 rate reaches theta_eat: at least ceil(theta_eat * window) spikes
        within a trailing window; the decision time is the spike that completes the count.
ESCAPE  one DNp01 spike (either side).
The earlier of the two wins. Neither within T_sim -> IDLE at T_sim. An exact tie (same 0.1 ms
step) goes to ESCAPE — see docs/ENGINEERED.md, E10.

All comparisons are made on integer time steps. Spike times arrive as floats (step * dt), and
the same step prints as 39.2 from one simulator and 39.199999999999996 from another; comparing
such values in milliseconds would let rounding decide a burst that spans exactly the window.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from flight_or_bite.lif.backend import TrialResult
from flight_or_bite.types import Action

DT_MS = 0.1  # simulation step of the model (configs/lif.yaml)


@dataclass(frozen=True)
class Decoded:
    action: Action
    t_sim_ms: float
    t_eat_ms: float | None  # when the MN9 criterion was met, if ever within the trial
    t_escape_ms: float | None  # first DNp01 spike, if any
    tie: bool = False


def spikes_needed(theta_hz: float, window_ms: float) -> int:
    return max(1, math.ceil(theta_hz * window_ms / 1e3 - 1e-9))


def to_steps(t_ms: np.ndarray | float, dt_ms: float = DT_MS):
    return np.rint(np.asarray(t_ms) / dt_ms).astype(np.int64)


def rate_crossing_ms(spike_t_ms: np.ndarray, theta_hz: float, window_ms: float,
                     dt_ms: float = DT_MS) -> float | None:  # fmt: skip
    """Time of the first spike that makes `spikes_needed` spikes fall within (t - window, t]."""
    k = spikes_needed(theta_hz, window_ms)
    step = np.sort(to_steps(spike_t_ms, dt_ms))
    if len(step) < k:
        return None
    span = step[k - 1 :] - step[: len(step) - k + 1]  # steps covered by k consecutive spikes
    hit = np.flatnonzero(span < round(window_ms / dt_ms))
    return round(float(step[k - 1 + hit[0]] * dt_ms), 6) if len(hit) else None


def decode(result: TrialResult, mn9: int, dnp01: np.ndarray, *, theta_eat_hz: float,
           eat_window_ms: float, t_sim_ms: float, dt_ms: float = DT_MS) -> Decoded:  # fmt: skip
    t_eat = rate_crossing_ms(result.times_of(mn9), theta_eat_hz, eat_window_ms, dt_ms)
    dn = result.spike_t_ms[np.isin(result.spike_i, dnp01)]
    t_escape = round(float(to_steps(dn, dt_ms).min() * dt_ms), 6) if len(dn) else None
    if t_eat is None and t_escape is None:
        return Decoded(Action.IDLE, t_sim_ms, None, None)
    eat_step = None if t_eat is None else int(to_steps(t_eat, dt_ms))
    escape_step = None if t_escape is None else int(to_steps(t_escape, dt_ms))
    if escape_step is not None and (eat_step is None or escape_step <= eat_step):
        return Decoded(Action.ESCAPE, t_escape, t_eat, t_escape, tie=eat_step == escape_step)
    return Decoded(Action.EAT, t_eat, t_eat, t_escape)
