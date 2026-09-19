"""Backend-independent trial interface (SPEC §4.1: step-wise run with early stopping)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class Stimulus:
    """Poisson drive, as in model.py: each event kicks `v` over threshold; no refractoriness."""

    neurons: np.ndarray  # model indices
    rates_hz: np.ndarray  # one rate per neuron

    def __post_init__(self) -> None:
        if len(self.neurons) != len(self.rates_hz):
            raise ValueError("neurons and rates_hz differ in length")
        if len(set(self.neurons.tolist())) != len(self.neurons):
            raise ValueError("duplicate stimulated neuron")

    @classmethod
    def uniform(cls, neurons: np.ndarray, rate_hz: float) -> Stimulus:
        neurons = np.asarray(neurons, dtype=np.int32)
        return cls(neurons, np.full(len(neurons), float(rate_hz)))


@dataclass(frozen=True)
class StopOnFirstSpike:
    """Stop as soon as any watched neuron has spiked."""

    neurons: np.ndarray


@dataclass
class TrialResult:
    spike_i: np.ndarray  # model index of each recorded spike
    spike_t_ms: np.ndarray  # its time, ms from stimulus onset
    t_sim_ms: float  # simulated time actually covered
    stopped_early: bool
    t_wall_ns: int
    meta: dict = field(default_factory=dict)

    def times_of(self, neuron: int) -> np.ndarray:
        return self.spike_t_ms[self.spike_i == neuron]

    def rate_hz(self, neuron: int) -> float:
        return 1e3 * np.count_nonzero(self.spike_i == neuron) / self.t_sim_ms

    @property
    def rtf(self) -> float:
        """Real-time factor: simulated time / wall time (SPEC §6.2)."""
        return (self.t_sim_ms / 1e3) / (self.t_wall_ns / 1e9)


class LIFBackend(Protocol):
    name: str
    t_load_s: float  # time spent building the network, reported separately from trials

    def run_trial(
        self,
        stimulus: Stimulus,
        t_max_ms: float,
        seed: int,
        stop: StopOnFirstSpike | None = None,
        silenced: np.ndarray | None = None,
    ) -> TrialResult: ...
