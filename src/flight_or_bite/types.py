"""Core types shared by the arena and all arbiters (SPEC §2, §4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

import numpy as np


class Action(StrEnum):
    EAT = "EAT"
    ESCAPE = "ESCAPE"
    IDLE = "IDLE"


@dataclass(frozen=True)
class Observation:
    """One trial's stimuli. All fields live in [0, 1]."""

    sugar: float
    bitter: float
    looming: float
    hunger: float

    def __post_init__(self) -> None:
        for name in ("sugar", "bitter", "looming", "hunger"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name}={value} is outside [0, 1]")


@dataclass
class Decision:
    probs: dict[Action, float]
    action: Action  # sampled from probs
    t_wall_ns: int  # wall-clock from request to ready action
    t_sim_ms: float | None = None  # connectome only; nobody else has a second clock (D10)
    meta: dict[str, Any] = field(default_factory=dict)  # cache_hit, backend, model_version, ...


@runtime_checkable
class Arbiter(Protocol):
    name: str

    def decide(self, obs: Observation, rng: np.random.Generator) -> Decision: ...
