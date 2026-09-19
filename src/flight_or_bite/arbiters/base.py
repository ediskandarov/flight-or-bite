"""Shared arbiter plumbing: every arbiter's decision time is measured the same way (SPEC §4.4)."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from flight_or_bite.types import Action, Decision, Observation

ACTIONS = tuple(Action)


def sample_action(probs: dict[Action, float], rng: np.random.Generator) -> Action:
    p = np.array([probs.get(a, 0.0) for a in ACTIONS], dtype=np.float64)
    if np.any(p < 0) or p.sum() <= 0:
        raise ValueError(f"invalid action probabilities: {probs}")
    return ACTIONS[int(rng.choice(len(ACTIONS), p=p / p.sum()))]


class TimedArbiter(ABC):
    """`decide` = policy + sampling inside one wall-clock measurement: request -> ready action."""

    name: str

    @abstractmethod
    def policy(self, obs: Observation) -> tuple[dict[Action, float], dict[str, Any]]:
        """Action probabilities and metadata (may include `t_sim_ms`)."""

    def decide(self, obs: Observation, rng: np.random.Generator) -> Decision:
        t0 = time.perf_counter_ns()
        probs, meta = self.policy(obs)
        action = sample_action(probs, rng)
        t_wall_ns = time.perf_counter_ns() - t0
        return Decision(
            probs=probs, action=action, t_wall_ns=t_wall_ns, t_sim_ms=meta.pop("t_sim_ms", None),
            meta=meta,
        )  # fmt: skip
