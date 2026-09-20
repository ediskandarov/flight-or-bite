"""The food-vs-threat environment (SPEC §3): a sequence of trials, no spatial navigation."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict

from flight_or_bite import prereg
from flight_or_bite.types import Action, Observation

TEST_ACCESS_LOG = Path("runs/test_access.log")

CAUSE_STARVATION = "starvation"
CAUSE_PREDATOR = "predator"
CAUSE_TOXIN = "toxin"
CAUSE_DEADLINE = "missed_deadline"  # killed by a threat on a trial lost to the deadline
CAUSE_CENSORED = "censored"  # alive at max_trials


class Gaussian(BaseModel):
    mean: float
    sd: float


class EnvConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    energy_start: float
    energy_max: float
    max_trials: int
    p_food: float
    sugar_range: tuple[float, float]
    p_toxic: float
    bitter_toxic_range: tuple[float, float]
    bitter_safe_range: tuple[float, float]
    p_threat: float
    looming_threat: Gaussian
    looming_safe: Gaussian
    metabolism: float
    eat_gain: float
    toxic_cost: float
    escape_cost: float
    p_death_eat: float
    p_death_idle: float
    deadline_ms: float | None = None
    seeds: dict[str, tuple[int, int]]

    def split_of(self, seed: int) -> str | None:
        return next((name for name, (lo, hi) in self.seeds.items() if lo <= seed <= hi), None)

    def seeds_of(self, split: str) -> range:
        lo, hi = self.seeds[split]
        return range(lo, hi + 1)


def load_env_config(path: Path = Path("configs/env.yaml")) -> EnvConfig:
    return EnvConfig.model_validate(yaml.safe_load(path.read_text()))


class SplitLocked(PermissionError):
    pass


def _require_frozen_prereg() -> None:
    try:
        prereg.check()
    except prereg.PreregError as e:
        raise SplitLocked(str(e)) from e


def check_split_access(cfg: EnvConfig, split: str, unlock_test: bool) -> None:
    """Fail early, before any run directory or log entry is created."""
    if split != "test":
        return
    if not unlock_test:
        raise SplitLocked("the test split is locked; pass --unlock-test")
    _require_frozen_prereg()


class Arena:
    """`reset(seed) -> obs`, `step(action) -> obs, done, info`. Deterministic by seed.

    Everything random in an episode — stimuli, the hidden threat and toxicity, and the death
    lottery — is drawn at reset and does not depend on the actions taken, so two arbiters on
    the same seed face the same world (common random numbers for paired comparisons).
    """

    def __init__(self, config: EnvConfig, *, unlock_test: bool = False) -> None:
        self.cfg = config
        self.unlock_test = unlock_test
        self._t = 0
        self._done = True

    def reset(self, seed: int) -> Observation:
        cfg = self.cfg
        if cfg.split_of(seed) == "test":
            self._authorise_test_access(seed)
        rng = np.random.default_rng(seed)
        n = cfg.max_trials
        food = rng.random(n) < cfg.p_food
        self.sugar = np.where(food, rng.uniform(*cfg.sugar_range, n), 0.0)
        self.toxic = food & (rng.random(n) < cfg.p_toxic)
        self.bitter = np.where(
            self.toxic,
            rng.uniform(*cfg.bitter_toxic_range, n),
            rng.uniform(*cfg.bitter_safe_range, n),
        )
        self.threat = rng.random(n) < cfg.p_threat
        self.looming = np.clip(
            np.where(
                self.threat,
                rng.normal(cfg.looming_threat.mean, cfg.looming_threat.sd, n),
                rng.normal(cfg.looming_safe.mean, cfg.looming_safe.sd, n),
            ),
            0.0,
            1.0,
        )
        self._death_draw = rng.random(n)
        self.seed = seed
        self.energy = cfg.energy_start
        self._t = 0
        self._done = False
        return self._observe()

    def _observe(self) -> Observation:
        t = self._t
        return Observation(
            sugar=float(self.sugar[t]),
            bitter=float(self.bitter[t]),
            looming=float(self.looming[t]),
            hunger=1.0 - self.energy / self.cfg.energy_max,
        )

    def step(
        self, action: Action, decision_time_ms: float | None = None
    ) -> tuple[Observation | None, bool, dict[str, Any]]:
        if self._done:
            raise RuntimeError("episode is over; call reset()")
        cfg, t = self.cfg, self._t
        missed = (
            cfg.deadline_ms is not None
            and decision_time_ms is not None
            and decision_time_ms > cfg.deadline_ms
        )
        if missed:
            action = Action.IDLE  # "did not make it" (SPEC §3)
        info: dict[str, Any] = {
            "trial": t, "action": action, "missed_deadline": missed,
            "threat": bool(self.threat[t]), "toxic": bool(self.toxic[t]),
        }  # fmt: skip

        p_death = {Action.EAT: cfg.p_death_eat, Action.IDLE: cfg.p_death_idle, Action.ESCAPE: 0.0}
        if self.threat[t] and self._death_draw[t] < p_death[action]:
            return self._finish(info, CAUSE_DEADLINE if missed else CAUSE_PREDATOR)

        energy = self.energy - cfg.metabolism
        poisoned = False
        if action is Action.EAT:
            energy += cfg.eat_gain * self.sugar[t]
            if self.toxic[t]:
                poisoned = energy > 0  # the toxin, not hunger, is what finishes the agent off
                energy -= cfg.toxic_cost * self.bitter[t]
        elif action is Action.ESCAPE:
            energy -= cfg.escape_cost
        self.energy = float(min(energy, cfg.energy_max))
        if self.energy <= 0:
            self.energy = 0.0
            return self._finish(info, CAUSE_TOXIN if poisoned else CAUSE_STARVATION)

        self._t += 1
        if self._t >= cfg.max_trials:
            return self._finish(info, CAUSE_CENSORED)
        info["energy"] = self.energy
        return self._observe(), False, info

    def _finish(self, info: dict[str, Any], cause: str) -> tuple[None, bool, dict[str, Any]]:
        self._done = True
        # lifetime = trials completed alive; the trial on which the agent dies does not count
        info.update(cause=cause, lifetime=self._t, energy=self.energy)
        return None, True, info

    def _authorise_test_access(self, seed: int) -> None:
        if not self.unlock_test:
            raise SplitLocked(f"seed {seed} is in the test split; pass --unlock-test")
        _require_frozen_prereg()
        TEST_ACCESS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with TEST_ACCESS_LOG.open("a") as f:
            stamp = datetime.now().astimezone().isoformat(timespec="seconds")
            f.write(f"{stamp}\tseed={seed}\t{' '.join(sys.argv)}\n")
