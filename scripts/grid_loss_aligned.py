"""Follow-up to grid_loss.py: grids whose nodes follow the environment's own structure.

Observations never fall in sugar (0, 0.2) or bitter (0.1, 0.3) (SPEC §3), so nodes at 0 / 0.2 and
0.1 / 0.3 keep interpolation from mixing "no food" with "food" and "safe" with "toxic".
"""

from __future__ import annotations

import shutil

import numpy as np

from flight_or_bite.arbiters.baselines import FixedPriorityArbiter
from flight_or_bite.arbiters.oracle import OracleArbiter
from flight_or_bite.arena.env import load_env_config
from flight_or_bite.eval.episodes import run_split
from flight_or_bite.eval.stats import paired_bootstrap
from flight_or_bite.policy_table.table import GridSpec, PolicyTable, TabularArbiter, build_table
from flight_or_bite.runlog import start_run, write_json

cfg = load_env_config()
seeds = cfg.seeds_of("dev")
lin = lambda n: [round(float(x), 6) for x in np.linspace(0, 1, n)]  # noqa: E731
SUGAR = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
BITTER = [0.0, 0.1, 0.3, 0.65, 1.0]
GRIDS = {
    "E aligned 6x5x5x3": {"sugar": SUGAR, "bitter": BITTER, "looming": lin(5), "hunger": lin(3)},
    "F aligned 6x5x11x5": {"sugar": SUGAR, "bitter": BITTER, "looming": lin(11), "hunger": lin(5)},
    "G aligned 6x5x21x9": {"sugar": SUGAR, "bitter": BITTER, "looming": lin(21), "hunger": lin(9)},
    "H aligned 6x5x41x17": {
        "sugar": SUGAR,
        "bitter": BITTER,
        "looming": lin(41),
        "hunger": lin(17),
    },
}
run_dir = start_run("grid-loss-aligned", {"grids": GRIDS}, seeds={"dev": [0, 999]})
rng = np.random.default_rng(1)
out = {}
for arbiter in (OracleArbiter(cfg), FixedPriorityArbiter()):
    direct = np.array([r.lifetime for r in run_split(cfg, arbiter, seeds)], dtype=float)
    out[arbiter.name] = {"direct": float(direct.mean()), "grids": {}}
    for label, axes in GRIDS.items():
        grid = GridSpec(axes=axes, n_rep=1, shard_points=1000, seed_base=1)
        tdir = run_dir / "tables" / arbiter.name / label.split()[0]
        build_table(arbiter, grid, tdir)
        tab = TabularArbiter(f"{arbiter.name}_table", PolicyTable.load(tdir))
        life = np.array([r.lifetime for r in run_split(cfg, tab, seeds)], dtype=float)
        d = paired_bootstrap(life, direct, rng)
        out[arbiter.name]["grids"][label] = {
            "points": int(np.prod(grid.shape)), "lifetime": float(life.mean()), "diff": d.mean_diff,
            "ci95": [d.ci_low, d.ci_high], "retained": float(life.mean() / direct.mean()),
        }  # fmt: skip
        print(
            arbiter.name,
            label,
            {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out[arbiter.name]["grids"][label].items()},
            flush=True,
        )
    shutil.rmtree(run_dir / "tables" / arbiter.name)
write_json(run_dir / "grid_loss.json", out)
print("DONE", run_dir)
