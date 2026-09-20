"""Motor decoding (SPEC §4.1, decision D25).

EAT     the sliding-window MN9 rate reaches theta_eat: at least ceil(theta_eat * window) spikes
        within a trailing window; the decision time is the spike that completes the count.
ESCAPE  one DNp01 spike (either side).
The earlier of the two wins. Neither within T_sim -> IDLE at T_sim. An exact tie (same 0.1 ms
step) goes to ESCAPE — see docs/ENGINEERED.md, E10.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from flight_or_bite.lif.backend import TrialResult
from flight_or_bite.types import Action


@dataclass(frozen=True)
class Decoded:
    action: Action
    t_sim_ms: float
    t_eat_ms: float | None  # when the MN9 criterion was met, if ever within the trial
    t_escape_ms: float | None  # first DNp01 spike, if any
    tie: bool = False


def spikes_needed(theta_hz: float, window_ms: float) -> int:
    return max(1, math.ceil(theta_hz * window_ms / 1e3 - 1e-9))


def rate_crossing_ms(spike_t_ms: np.ndarray, theta_hz: float, window_ms: float) -> float | None:
    """Time of the first spike that makes `spikes_needed` spikes fall within (t - window, t]."""
    k = spikes_needed(theta_hz, window_ms)
    t = np.sort(spike_t_ms)
    if len(t) < k:
        return None
    span = t[k - 1 :] - t[: len(t) - k + 1]  # time covered by each run of k consecutive spikes
    hit = np.flatnonzero(span < window_ms)
    return float(t[k - 1 + hit[0]]) if len(hit) else None


def decode(result: TrialResult, mn9: int, dnp01: np.ndarray, *, theta_eat_hz: float,
           eat_window_ms: float, t_sim_ms: float) -> Decoded:  # fmt: skip
    t_eat = rate_crossing_ms(result.times_of(mn9), theta_eat_hz, eat_window_ms)
    dn = result.spike_t_ms[np.isin(result.spike_i, dnp01)]
    t_escape = float(dn.min()) if len(dn) else None
    if t_eat is None and t_escape is None:
        return Decoded(Action.IDLE, t_sim_ms, None, None)
    if t_escape is not None and (t_eat is None or t_escape <= t_eat):
        return Decoded(Action.ESCAPE, t_escape, t_eat, t_escape, tie=t_eat == t_escape)
    return Decoded(Action.EAT, t_eat, t_eat, t_escape)
