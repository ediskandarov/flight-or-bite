"""Run arbiters through episodes of the arena and collect per-episode results."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

import numpy as np

from flight_or_bite.arena.env import Arena, EnvConfig
from flight_or_bite.types import Action, Arbiter


@dataclass
class EpisodeResult:
    arbiter: str
    seed: int
    lifetime: int  # trials completed alive, censored at max_trials
    cause: str
    final_energy: float
    mean_energy: float  # over the trials the agent lived through
    n_eat: int
    n_escape: int
    n_idle: int
    n_missed_deadline: int
    t_wall_ns_median: float

    def as_dict(self) -> dict:
        return asdict(self)


def arbiter_rng(seed: int, name: str) -> np.random.Generator:
    """Action sampling has its own stream, so it never disturbs the world's randomness."""
    return np.random.default_rng([seed, sum(name.encode())])


def run_episode(arena: Arena, arbiter: Arbiter, seed: int, *, clock: str = "wall") -> EpisodeResult:
    """`clock`: which decision time is held against the deadline — 'wall' or 'native' (t_sim)."""
    obs = arena.reset(seed)
    rng = arbiter_rng(seed, arbiter.name)
    counts = dict.fromkeys(Action, 0)
    energies, walls, missed = [], [], 0
    done, info = False, {}
    while not done:
        energies.append((1.0 - obs.hunger) * arena.cfg.energy_max)
        decision = arbiter.decide(obs, rng)
        walls.append(decision.t_wall_ns)
        t_ms = decision.t_wall_ns / 1e6
        if clock == "native" and decision.t_sim_ms is not None:
            t_ms = decision.t_sim_ms
        obs, done, info = arena.step(decision.action, decision_time_ms=t_ms)
        counts[info["action"]] += 1
        missed += info["missed_deadline"]
    return EpisodeResult(
        arbiter=arbiter.name, seed=seed, lifetime=info["lifetime"], cause=info["cause"],
        final_energy=info["energy"], mean_energy=float(np.mean(energies)),
        n_eat=counts[Action.EAT], n_escape=counts[Action.ESCAPE], n_idle=counts[Action.IDLE],
        n_missed_deadline=missed, t_wall_ns_median=float(np.median(walls)),
    )  # fmt: skip


def run_split(cfg: EnvConfig, arbiter: Arbiter, seeds: Iterable[int], *, unlock_test: bool = False,
              clock: str = "wall") -> list[EpisodeResult]:  # fmt: skip
    arena = Arena(cfg, unlock_test=unlock_test)
    return [run_episode(arena, arbiter, seed, clock=clock) for seed in seeds]
