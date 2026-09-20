"""One decoded connectome trial under the frozen encoding (SPEC §4.1, decisions D25, D36).

Every channel draws its Poisson kicks from its own RNG stream keyed by (seed, channel), so for a
given seed a channel's input spikes are bit-identical whatever the other channels do. That is
what makes paired comparisons (McNemar) across conditions meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from flight_or_bite.lif.backend import Stimulus, StopOnFirstSpike
from flight_or_bite.lif.circuits import load_circuits, resolve
from flight_or_bite.lif.data import load_manifest
from flight_or_bite.lif.decoder import Decoded, decode, spikes_needed
from flight_or_bite.lif.encoding import Encoding, load_encoding
from flight_or_bite.lif.event_backend import EventBackend
from flight_or_bite.lif.graph import Connectome, load_connectome
from flight_or_bite.lif.params import LIFParams, load_params
from flight_or_bite.types import Observation

CHANNEL_ID = {"sugar": 1, "bitter": 2, "looming": 3, "looming_subset": 4}
FRACTION_RATE_HZ = 100.0  # population code of the looming channel (G6 robustness check only)


@dataclass(frozen=True)
class Trial:
    decoded: Decoded
    mn9_rate_hz: float
    dnp01_spiked: bool
    n_spikes: int
    n_active: int
    t_wall_ns: int


def load_real_connectome(params: LIFParams | None = None) -> Connectome:
    params = params or load_params()
    return load_connectome(load_manifest(Path("configs/data.yaml")), params.connectome_version, Path("data"))


class TrialRunner:
    def __init__(self, connectome: Connectome, params: LIFParams | None = None,
                 encoding: Encoding | None = None, *, looming_fraction: float | None = None) -> None:  # fmt: skip
        self.params = params or load_params()
        self.enc = encoding or load_encoding()
        self.looming_fraction = looming_fraction  # None = rate code; else f_max of the fraction code
        circuits = load_circuits()
        self.sets = {
            "sugar": resolve(connectome, circuits["sugar_grn_right"]),
            "bitter": resolve(connectome, circuits["bitter_grn_shiu"]),
            "looming": np.concatenate([resolve(connectome, circuits["lplc2"]), resolve(connectome, circuits["lc4"])]),
        }
        self.mn9 = int(resolve(connectome, circuits["mn9"])[0])
        self.dnp01 = resolve(connectome, circuits["dnp01"])
        self.named = {k: resolve(connectome, circuits[k]) for k in ("m_loom", "cl20", "dnp01", "mn9")}
        self.backend = EventBackend(connectome, self.params)
        self.n_steps = round(self.enc.t_sim_ms / self.params.dt_ms)

    def _stream(self, seed: int, channel: str) -> np.random.Generator:
        return np.random.default_rng([seed, CHANNEL_ID[channel]])

    def _kicks(self, neurons: np.ndarray, rate_hz: float, seed: int, channel: str):
        p = rate_hz * self.params.dt_ms * 1e-3
        if p > 1:
            raise ValueError(f"{channel}: rate {rate_hz} Hz exceeds 1/dt")
        steps, cols = np.nonzero(self._stream(seed, channel).random((self.n_steps, len(neurons))) < p)
        return steps.astype(np.int64), neurons[cols].astype(np.int32)

    def run(self, obs: Observation, seed: int, *, ablated: np.ndarray | None = None,
            theta_eat_hz: float | None = None, early_stop: bool = False) -> Trial:  # fmt: skip
        """`early_stop`: end the simulation at the decoder's event (online use). The decoded
        action and t_sim are the same as for the full trial; rates and counts then cover only the
        simulated part."""
        rates = self.enc.rates(obs)
        parts, driven = [], []
        for channel in ("sugar", "bitter"):
            if rates[channel] > 0:
                parts.append(self._kicks(self.sets[channel], rates[channel], seed, channel))
                driven.append(self.sets[channel])
        if obs.looming > 0:
            loom = self.sets["looming"]
            if self.looming_fraction is None:
                parts.append(self._kicks(loom, rates["looming"], seed, "looming"))
                driven.append(loom)
            else:
                x = obs.looming * self.looming_fraction * len(loom)
                rng = self._stream(seed, "looming_subset")
                k = int(np.floor(x)) + int(rng.random() < x - np.floor(x))
                subset = np.sort(rng.choice(loom, size=k, replace=False)) if k else loom[:0]
                parts.append(self._kicks(subset, FRACTION_RATE_HZ, seed, "looming"))
                driven.append(subset)
        steps = np.concatenate([p[0] for p in parts]) if parts else np.empty(0, np.int64)
        neurons = np.concatenate([p[1] for p in parts]) if parts else np.empty(0, np.int32)
        order = np.argsort(steps, kind="stable")
        marked = np.concatenate(driven).astype(np.int32) if driven else np.empty(0, np.int32)
        theta = theta_eat_hz or self.enc.theta_eat_hz
        stop = burst = None
        if early_stop:
            stop = StopOnFirstSpike(self.dnp01)
            burst = (self.mn9, spikes_needed(theta, self.enc.eat_window_ms),
                     round(self.enc.eat_window_ms / self.params.dt_ms))  # fmt: skip
        result = self.backend.run_trial(
            Stimulus(marked, np.zeros(len(marked))), self.enc.t_sim_ms, seed=seed,
            kicks=(steps[order], neurons[order]), ablated=ablated, stop=stop, stop_on_burst=burst,
        )  # fmt: skip
        decoded = decode(result, self.mn9, self.dnp01, theta_eat_hz=theta_eat_hz or self.enc.theta_eat_hz,
                         eat_window_ms=self.enc.eat_window_ms, t_sim_ms=self.enc.t_sim_ms)  # fmt: skip
        return Trial(decoded, result.rate_hz(self.mn9), decoded.t_escape_ms is not None,
                     int(result.spike_i.size), int(np.unique(result.spike_i).size), result.t_wall_ns)  # fmt: skip
