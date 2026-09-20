"""Sensory encoding (SPEC §4.1, decision D25): observation -> Poisson drive of neuron sets."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict

from flight_or_bite.lif.backend import Stimulus
from flight_or_bite.types import Observation


class Encoding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    t_sim_ms: float
    r_max_sugar_hz: float
    r_max_bitter_hz: float
    r_max_looming_hz: float
    theta_eat_hz: float
    eat_window_ms: float
    alpha: float | None = None  # hunger gain on the sugar channel; None = not set, treated as 0
    calibration_run: str | None = None

    def rates(self, obs: Observation) -> dict[str, float]:
        gain = 1.0 + (self.alpha or 0.0) * obs.hunger
        return {
            "sugar": obs.sugar * self.r_max_sugar_hz * gain,
            "bitter": obs.bitter * self.r_max_bitter_hz,
            "looming": obs.looming * self.r_max_looming_hz,
        }

    def stimulus(self, obs: Observation, sets: dict[str, np.ndarray]) -> Stimulus:
        """`sets` maps channel name -> model indices; channels absent from `sets` are skipped."""
        rates = self.rates(obs)
        neurons = np.concatenate([sets[c] for c in sets]).astype(np.int32)
        hz = np.concatenate([np.full(len(sets[c]), rates[c]) for c in sets])
        return Stimulus(neurons, hz)


def load_encoding(path: Path = Path("configs/encoding.yaml")) -> Encoding:
    return Encoding.model_validate(yaml.safe_load(path.read_text()))
