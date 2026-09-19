"""Baselines (SPEC §4.4). They also give the low end of the decision-time scale."""

from __future__ import annotations

from typing import Any

from flight_or_bite.arbiters.base import ACTIONS, TimedArbiter
from flight_or_bite.types import Action, Observation


def one_hot(action: Action) -> dict[Action, float]:
    return {a: float(a is action) for a in ACTIONS}


class RandomArbiter(TimedArbiter):
    name = "random"

    def policy(self, obs: Observation) -> tuple[dict[Action, float], dict[str, Any]]:
        return {a: 1.0 / len(ACTIONS) for a in ACTIONS}, {}


class FixedPriorityArbiter(TimedArbiter):
    """looming > 0.5 -> ESCAPE; else sugar > 0 and bitter < 0.3 -> EAT; else IDLE."""

    name = "fixed_priority"

    def policy(self, obs: Observation) -> tuple[dict[Action, float], dict[str, Any]]:
        if obs.looming > 0.5:
            return one_hot(Action.ESCAPE), {}
        if obs.sugar > 0 and obs.bitter < 0.3:
            return one_hot(Action.EAT), {}
        return one_hot(Action.IDLE), {}
