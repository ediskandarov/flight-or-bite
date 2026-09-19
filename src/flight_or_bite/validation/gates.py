"""Validity gates (SPEC §5). Each gate writes reports/gates/<gate>.json."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from flight_or_bite.lif.backend import LIFBackend, Stimulus


@dataclass
class GateResult:
    gate: str
    passed: bool
    metric: float
    threshold: float
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def g1_sugar_to_mn9(
    backend: LIFBackend,
    sugar_neurons: np.ndarray,
    mn9: int,
    *,
    r_max_hz: float,
    t_sim_ms: float,
    levels: int,
    n_rep: int,
    seed_base: int,
    threshold: float,
) -> GateResult:
    """G1: MN9 rate grows monotonically with sugar (Spearman rho over all trials > threshold)."""
    sugar = np.linspace(0.0, 1.0, levels)
    rates = np.empty((levels, n_rep))
    for li, s in enumerate(sugar):
        stim = Stimulus.uniform(sugar_neurons, s * r_max_hz)
        for rep in range(n_rep):
            trial = backend.run_trial(stim, t_sim_ms, seed=seed_base + li * n_rep + rep)
            rates[li, rep] = trial.rate_hz(mn9)

    rho = float(spearmanr(np.repeat(sugar, n_rep), rates.ravel()).statistic)
    mean = rates.mean(axis=1)
    rho_means = float(spearmanr(sugar, mean).statistic)
    return GateResult(
        gate="G1",
        passed=bool(rho > threshold),  # NaN (constant MN9 rate) fails
        metric=rho,
        threshold=threshold,
        details={
            "backend": backend.name,
            "n_sugar_neurons": int(len(sugar_neurons)),
            "r_max_hz": r_max_hz,
            "t_sim_ms": t_sim_ms,
            "n_rep": n_rep,
            "sugar": sugar.round(6).tolist(),
            "mn9_rate_hz_mean": mean.round(3).tolist(),
            "mn9_rate_hz_sd": rates.std(axis=1).round(3).tolist(),
            "rho_over_level_means": rho_means,
            "strictly_increasing_means": bool(np.all(np.diff(mean) > 0)),
        },
    )
