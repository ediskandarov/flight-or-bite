"""Grid loss as a function of how sharp the policy is (exploratory, no Jev calls).

Soft oracle: P(action) ∝ exp(Q(action) / tau), Q from the oracle's value function (units: expected
remaining trials). tau -> 0 is the deterministic oracle; large tau approaches a uniform policy.
Each soft policy is played directly (sampling from its exact probabilities) and from tables.
"""

from __future__ import annotations

import shutil

import numpy as np

from flight_or_bite.arbiters.base import ACTIONS, TimedArbiter
from flight_or_bite.arbiters.oracle import OracleArbiter
from flight_or_bite.arena.env import load_env_config
from flight_or_bite.eval.episodes import run_split
from flight_or_bite.eval.stats import paired_bootstrap
from flight_or_bite.policy_table.table import GridSpec, PolicyTable, TabularArbiter, build_table
from flight_or_bite.runlog import start_run, write_json
from flight_or_bite.types import Observation

cfg = load_env_config()
seeds = cfg.seeds_of("dev")
oracle = OracleArbiter(cfg)
lin = lambda n: [round(float(x), 6) for x in np.linspace(0, 1, n)]  # noqa: E731
SUGAR, BITTER = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], [0.0, 0.1, 0.3, 0.65, 1.0]
GRIDS = {
    "A 5x3x5x3": {"sugar": lin(5), "bitter": lin(3), "looming": lin(5), "hunger": lin(3)},
    "F aligned 6x5x11x5": {"sugar": SUGAR, "bitter": BITTER, "looming": lin(11), "hunger": lin(5)},
    "G aligned 6x5x21x9": {"sugar": SUGAR, "bitter": BITTER, "looming": lin(21), "hunger": lin(9)},
}
TAUS = (0.5, 2.0, 8.0, 32.0)
PROBE = [Observation(0.6, 0.05, x, 0.5) for x in (0.2, 0.4, 0.5, 0.6, 0.8)]


class SoftOracle(TimedArbiter):
    def __init__(self, tau: float) -> None:
        self.tau, self.name = tau, f"soft_oracle_tau{tau}"

    def policy(self, obs):
        q = oracle.q_values(obs)
        z = np.array([q[a] for a in ACTIONS]) / self.tau
        p = np.exp(z - z.max())
        p /= p.sum()
        return {a: float(x) for a, x in zip(ACTIONS, p, strict=True)}, {}


run_dir = start_run("grid-loss-smooth", {"taus": TAUS, "grids": GRIDS}, seeds={"dev": [0, 999]})
rng = np.random.default_rng(1)
out = {}
for tau in TAUS:
    arb = SoftOracle(tau)
    direct = np.array([r.lifetime for r in run_split(cfg, arb, seeds)], dtype=float)
    curve = [round(arb.policy(o)[0][ACTIONS[1]], 3) for o in PROBE]  # p_escape at looming 0.2..0.8
    out[tau] = {
        "direct": float(direct.mean()),
        "p_escape_at_looming_0.2_0.4_0.5_0.6_0.8": curve,
        "grids": {},
    }
    for label, axes in GRIDS.items():
        tdir = run_dir / "tables" / label.split()[0]
        build_table(arb, GridSpec(axes=axes, n_rep=1, shard_points=1000, seed_base=1), tdir)
        life = np.array(
            [r.lifetime for r in run_split(cfg, TabularArbiter("t", PolicyTable.load(tdir)), seeds)],
            dtype=float,
        )
        d = paired_bootstrap(life, direct, rng)
        out[tau]["grids"][label] = {"lifetime": float(life.mean()), "diff": d.mean_diff, "ci95": [d.ci_low, d.ci_high],
                                    "retained": float(life.mean() / direct.mean())}  # fmt: skip
        shutil.rmtree(tdir)
    print(
        tau,
        out[tau]["direct"],
        curve,
        {k: round(v["retained"], 3) for k, v in out[tau]["grids"].items()},
        flush=True,
    )
write_json(run_dir / "grid_loss_smooth.json", {str(k): v for k, v in out.items()})
print("DONE", run_dir)
