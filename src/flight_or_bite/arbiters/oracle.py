"""OracleArbiter (SPEC §4.4): Bayesian threat posterior from `looming`, value iteration over a
discretised energy axis. It sees only the observation, never the hidden threat or toxicity.

Objective: expected number of trials survived within the episode limit. Backward induction gives
a time-dependent value V_t(energy); `decide(obs, rng)` carries no trial index, so the arbiter
acts with the far-from-the-horizon value (V_1) on every trial — see docs/ENGINEERED.md, V2.
"""

from __future__ import annotations

from math import erf, exp, pi, sqrt
from typing import Any

import numpy as np

from flight_or_bite.arbiters.base import TimedArbiter
from flight_or_bite.arbiters.baselines import one_hot
from flight_or_bite.arena.env import EnvConfig, Gaussian
from flight_or_bite.types import Action, Observation

# Exact ties are common once the value saturates (plenty of energy, nothing at stake): prefer the
# action that costs nothing, then eating, and escape only when it is strictly better.
TIE_BREAK = (Action.IDLE, Action.EAT, Action.ESCAPE)


def _cdf(x: float, g: Gaussian) -> float:
    return 0.5 * (1.0 + erf((x - g.mean) / (g.sd * sqrt(2.0))))


def _pdf(x: float, g: Gaussian) -> float:
    return exp(-0.5 * ((x - g.mean) / g.sd) ** 2) / (g.sd * sqrt(2.0 * pi))


def threat_posterior(looming: float, cfg: EnvConfig) -> float:
    """P(threat | looming) for clip(N) likelihoods: densities inside (0, 1), masses at the ends."""
    if looming <= 0.0:
        like_t, like_s = _cdf(0.0, cfg.looming_threat), _cdf(0.0, cfg.looming_safe)
    elif looming >= 1.0:
        like_t, like_s = 1.0 - _cdf(1.0, cfg.looming_threat), 1.0 - _cdf(1.0, cfg.looming_safe)
    else:
        like_t, like_s = _pdf(looming, cfg.looming_threat), _pdf(looming, cfg.looming_safe)
    num = cfg.p_threat * like_t
    den = num + (1.0 - cfg.p_threat) * like_s
    return num / den if den > 0 else cfg.p_threat


def is_toxic(obs: Observation, cfg: EnvConfig) -> bool:
    """Exact: the toxic and safe bitter ranges do not overlap."""
    return obs.sugar > 0 and obs.bitter >= cfg.bitter_toxic_range[0]


class OracleArbiter(TimedArbiter):
    name = "oracle"

    def __init__(self, cfg: EnvConfig, *, n_energy: int = 201, n_sugar: int = 16,
                 n_bitter: int = 8, n_looming: int = 50) -> None:  # fmt: skip
        self.cfg = cfg
        self.energy_grid = np.linspace(0.0, cfg.energy_max, n_energy)
        self.values = self._solve(n_sugar, n_bitter, n_looming)  # [max_trials + 1, n_energy]
        self.v_next = self.values[min(1, cfg.max_trials)]

    # -- dynamic programming --------------------------------------------------------------
    def _looming_quadrature(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        """Weights and threat posteriors for a binned looming observation (incl. end masses)."""
        cfg = self.cfg
        edges = np.linspace(0.0, 1.0, n + 1)

        def masses(g: Gaussian) -> np.ndarray:
            c = np.array([_cdf(e, g) for e in edges])
            return np.concatenate([[c[0]], np.diff(c), [1.0 - c[-1]]])

        m_t, m_s = masses(cfg.looming_threat), masses(cfg.looming_safe)
        weight = cfg.p_threat * m_t + (1.0 - cfg.p_threat) * m_s
        posterior = np.divide(cfg.p_threat * m_t, weight, out=np.zeros_like(weight), where=weight > 0)
        return weight, posterior

    def _food_quadrature(self, n_sugar: int, n_bitter: int) -> tuple[np.ndarray, np.ndarray]:
        """Weights and energy gain of EAT for: no food, safe food, toxic food."""
        cfg = self.cfg
        mid = lambda lo, hi, n: lo + (np.arange(n) + 0.5) * (hi - lo) / n  # noqa: E731
        sugar = mid(*cfg.sugar_range, n_sugar)
        bitter = mid(*cfg.bitter_toxic_range, n_bitter)
        safe_gain = cfg.eat_gain * sugar
        toxic_gain = (safe_gain[:, None] - cfg.toxic_cost * bitter[None, :]).ravel()
        gain = np.concatenate([[0.0], safe_gain, toxic_gain])
        weight = np.concatenate([
            [1.0 - cfg.p_food],
            np.full(n_sugar, cfg.p_food * (1.0 - cfg.p_toxic) / n_sugar),
            np.full(n_sugar * n_bitter, cfg.p_food * cfg.p_toxic / (n_sugar * n_bitter)),
        ])  # fmt: skip
        return weight, gain

    def _continuation(self, energy: np.ndarray, v_next: np.ndarray) -> np.ndarray:
        """1 + V(e') if the agent is alive after the energy update, else 0."""
        e = np.minimum(energy, self.cfg.energy_max)
        return np.where(e > 0, 1.0 + np.interp(e, self.energy_grid, v_next), 0.0)

    def _solve(self, n_sugar: int, n_bitter: int, n_looming: int) -> np.ndarray:
        cfg, grid = self.cfg, self.energy_grid
        w_loom, p_thr = self._looming_quadrature(n_looming)
        w_food, gain = self._food_quadrature(n_sugar, n_bitter)
        values = np.zeros((cfg.max_trials + 1, len(grid)))
        base = grid - cfg.metabolism
        for t in range(cfg.max_trials - 1, -1, -1):
            v = values[t + 1]
            cont_eat = self._continuation(base[None, :] + gain[:, None], v)  # [food, energy]
            cont_escape = self._continuation(base - cfg.escape_cost, v)  # [energy]
            cont_idle = self._continuation(base, v)
            q_eat = (1.0 - p_thr * cfg.p_death_eat)[None, :, None] * cont_eat[:, None, :]
            q_idle = (1.0 - p_thr * cfg.p_death_idle)[:, None] * cont_idle[None, :]
            q_rest = np.maximum(q_idle, cont_escape[None, :])  # [looming, energy]
            best = np.maximum(q_eat, q_rest[None, :, :])  # [food, looming, energy]
            values[t] = np.einsum("f,l,fle->e", w_food, w_loom, best)
            values[t, 0] = 0.0  # energy 0 is death
        return values

    # -- acting -----------------------------------------------------------------------------
    def q_values(self, obs: Observation) -> dict[Action, float]:
        cfg = self.cfg
        energy = (1.0 - obs.hunger) * cfg.energy_max
        p_thr = threat_posterior(obs.looming, cfg)
        gain = cfg.eat_gain * obs.sugar - (cfg.toxic_cost * obs.bitter if is_toxic(obs, cfg) else 0.0)
        base = energy - cfg.metabolism
        cont = lambda e: float(self._continuation(np.array([e]), self.v_next)[0])  # noqa: E731
        return {
            Action.EAT: (1.0 - p_thr * cfg.p_death_eat) * cont(base + gain),
            Action.ESCAPE: cont(base - cfg.escape_cost),
            Action.IDLE: (1.0 - p_thr * cfg.p_death_idle) * cont(base),
        }

    def policy(self, obs: Observation) -> tuple[dict[Action, float], dict[str, Any]]:
        q = self.q_values(obs)
        best = max(TIE_BREAK, key=q.__getitem__)  # max() keeps the first of equal candidates
        return one_hot(best), {"q": {a.value: v for a, v in q.items()},
                               "p_threat": threat_posterior(obs.looming, self.cfg)}  # fmt: skip
