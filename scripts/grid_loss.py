"""How much does tabulating a KNOWN policy on a grid cost? (exploratory, informs the grid size)

The oracle and fixed_priority are tabulated on candidate grids and then played from the table on
the 1000 dev seeds; the result is compared with playing them directly on the same seeds. Whatever
is lost here is lost to the grid and the interpolation, not to the arbiter.
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
GRIDS = {"A 5x3x5x3": (5, 3, 5, 3), "B 7x5x7x5": (7, 5, 7, 5), "C 9x5x9x5": (9, 5, 9, 5),
         "D 11x5x11x9": (11, 5, 11, 9)}  # fmt: skip
run_dir = start_run("grid-loss", {"grids": GRIDS, "env": cfg.model_dump()}, seeds={"dev": [0, 999]})
rng = np.random.default_rng(1)
out = {}
for arbiter in (OracleArbiter(cfg), FixedPriorityArbiter()):
    direct = np.array([r.lifetime for r in run_split(cfg, arbiter, seeds)], dtype=float)
    out[arbiter.name] = {"direct": float(direct.mean()), "grids": {}}
    for label, (ns, nb, nl, nh) in GRIDS.items():
        grid = GridSpec(
            axes={"sugar": lin(ns), "bitter": lin(nb), "looming": lin(nl), "hunger": lin(nh)},
            n_rep=1,
            shard_points=500,
            seed_base=1,
        )  # deterministic arbiters: 1 repeat
        tdir = run_dir / "tables" / arbiter.name / label.split()[0]
        build_table(arbiter, grid, tdir)
        tab = TabularArbiter(f"{arbiter.name}_table", PolicyTable.load(tdir))
        life = np.array([r.lifetime for r in run_split(cfg, tab, seeds)], dtype=float)
        d = paired_bootstrap(life, direct, rng)
        out[arbiter.name]["grids"][label] = {
            "points": ns * nb * nl * nh, "lifetime": float(life.mean()),
            "diff": d.mean_diff, "ci95": [d.ci_low, d.ci_high], "retained": float(life.mean() / direct.mean()),
        }  # fmt: skip
        print(arbiter.name, label, out[arbiter.name]["grids"][label], flush=True)
    shutil.rmtree(run_dir / "tables" / arbiter.name)
write_json(run_dir / "grid_loss.json", out)
print("DONE", run_dir)
