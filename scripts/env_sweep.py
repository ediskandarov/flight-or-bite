"""Environment sweep on dev (decision D28): p_food x eat_gain, oracle re-solved for each config.

Target stated by the spec's author: a configuration in which 25-75% of the oracle's deaths are
from starvation. This script reports; it does not choose.
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from flight_or_bite.arbiters.baselines import FixedPriorityArbiter, RandomArbiter
from flight_or_bite.arbiters.oracle import OracleArbiter
from flight_or_bite.arena.env import load_env_config
from flight_or_bite.eval.episodes import run_split
from flight_or_bite.eval.stats import bootstrap_mean_ci
from flight_or_bite.runlog import start_run, write_json

base = load_env_config()
seeds = base.seeds_of("dev")
CONFIGS = [("SPEC default", base.p_food, base.eat_gain)] + [
    (f"p_food {p}, G {g}", p, g) for p in (0.3, 0.4) for g in (8.0, 10.0)
]
run_dir = start_run(
    "env-sweep", {"configs": CONFIGS, "base": base.model_dump()}, seeds={"dev": [0, 999]}
)
rng = np.random.default_rng(20260920)
out = []
for label, p_food, gain in CONFIGS:
    cfg = base.model_copy(update={"p_food": p_food, "eat_gain": gain})
    row = {"label": label, "p_food": p_food, "eat_gain": gain}
    for arb in (OracleArbiter(cfg), FixedPriorityArbiter(), RandomArbiter()):
        res = run_split(cfg, arb, seeds)
        life = np.array([r.lifetime for r in res], dtype=float)
        causes = Counter(r.cause for r in res)
        deaths = len(res) - causes.get("censored", 0)
        lo, hi = bootstrap_mean_ci(life, rng)
        row[arb.name] = {
            "lifetime": float(life.mean()), "ci95": [lo, hi], "median": float(np.median(life)),
            "causes_share_of_episodes": {k: v / len(res) for k, v in causes.items()},
            "deaths": deaths,
            "starvation_share_of_deaths": causes.get("starvation", 0) / deaths if deaths else None,
            "toxin_share_of_deaths": causes.get("toxin", 0) / deaths if deaths else None,
            "predator_share_of_deaths": causes.get("predator", 0) / deaths if deaths else None,
            "mean_energy": float(np.mean([r.mean_energy for r in res])),
            "actions": {k: float(np.mean([getattr(r, f"n_{k}") / max(r.n_eat + r.n_escape + r.n_idle, 1) for r in res]))
                        for k in ("eat", "escape", "idle")},
        }  # fmt: skip
    o = row["oracle"]
    print(
        label,
        "| oracle life",
        round(o["lifetime"], 1),
        "| starvation share of deaths",
        round(o["starvation_share_of_deaths"], 3),
        "| predator",
        round(o["predator_share_of_deaths"], 3),
        "| censored",
        round(o["causes_share_of_episodes"].get("censored", 0), 3),
        "| fixed",
        round(row["fixed_priority"]["lifetime"], 1),
        "| random",
        round(row["random"]["lifetime"], 1),
        flush=True,
    )
    out.append(row)
write_json(run_dir / "env_sweep.json", out)
print("DONE", run_dir)
