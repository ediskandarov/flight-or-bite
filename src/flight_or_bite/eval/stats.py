"""Statistics for paired comparisons on shared seeds (SPEC §7)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

N_RESAMPLES = 10_000


@dataclass(frozen=True)
class PairedDifference:
    mean_diff: float  # mean(a) - mean(b)
    ci_low: float
    ci_high: float

    @property
    def significant(self) -> bool:
        """A win only if the 95% CI excludes zero."""
        return self.ci_low > 0 or self.ci_high < 0


def bootstrap_mean_ci(
    x: np.ndarray, rng: np.random.Generator, n: int = N_RESAMPLES
) -> tuple[float, float]:
    x = np.asarray(x, dtype=np.float64)
    means = x[rng.integers(0, len(x), size=(n, len(x)))].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def paired_bootstrap(a: np.ndarray, b: np.ndarray, rng: np.random.Generator,
                     n: int = N_RESAMPLES) -> PairedDifference:  # fmt: skip
    """Bootstrap over episodes (seeds), resampling the per-seed differences."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError("paired samples must have the same shape")
    lo, hi = bootstrap_mean_ci(a - b, rng, n)
    return PairedDifference(float((a - b).mean()), lo, hi)


def percent_of_oracle(lifetime: float, lifetime_random: float, lifetime_oracle: float) -> float:
    """(L - L_random) / (L_oracle - L_random), SPEC §7."""
    return (lifetime - lifetime_random) / (lifetime_oracle - lifetime_random)
