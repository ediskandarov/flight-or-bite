"""Supplement to env_sweep.py (NOT requested by the author): where in the neighbourhood does the
oracle's starvation share reach 25-75%? Same protocol, 1000 dev episodes, oracle re-solved."""

from __future__ import annotations

from collections import Counter

import numpy as np

from flight_or_bite.arbiters.baselines import FixedPriorityArbiter
from flight_or_bite.arbiters.oracle import OracleArbiter
from flight_or_bite.arena.env import load_env_config
from flight_or_bite.eval.episodes import run_split
from flight_or_bite.runlog import start_run, write_json

base = load_env_config()
seeds = base.seeds_of("dev")
VARIANTS = [
    {"p_food": 0.2, "eat_gain": 8.0}, {"p_food": 0.2, "eat_gain": 10.0}, {"p_food": 0.3, "eat_gain": 6.0},
    {"p_food": 0.3, "eat_gain": 8.0, "p_threat": 0.1}, {"p_food": 0.3, "eat_gain": 10.0, "p_threat": 0.1},
    {"p_food": 0.4, "eat_gain": 8.0, "p_threat": 0.1}, {"p_food": 0.4, "eat_gain": 10.0, "p_threat": 0.1},
    {"p_food": 0.3, "eat_gain": 8.0, "p_death_eat": 0.3, "p_death_idle": 0.15},
    {"p_food": 0.4, "eat_gain": 10.0, "p_death_eat": 0.3, "p_death_idle": 0.15},
    {"p_food": 0.3, "eat_gain": 8.0, "escape_cost": 1.0}, {"p_food": 0.4, "eat_gain": 10.0, "escape_cost": 1.0},
]  # fmt: skip
run_dir = start_run("env-sweep-extra", {"variants": VARIANTS}, seeds={"dev": [0, 999]})
out = []
for change in VARIANTS:
    cfg = base.model_copy(update=change)
    row = {"change": change}
    for arb in (OracleArbiter(cfg), FixedPriorityArbiter()):
        res = run_split(cfg, arb, seeds)
        causes = Counter(r.cause for r in res)
        deaths = len(res) - causes.get("censored", 0)
        row[arb.name] = {"lifetime": float(np.mean([r.lifetime for r in res])), "censored": causes.get("censored", 0) / len(res),
                         "starvation_share_of_deaths": causes.get("starvation", 0) / deaths if deaths else None,
                         "predator_share_of_deaths": causes.get("predator", 0) / deaths if deaths else None}  # fmt: skip
    o, f = row["oracle"], row["fixed_priority"]
    print(
        change,
        "| oracle",
        round(o["lifetime"], 1),
        "starv",
        round(o["starvation_share_of_deaths"], 3),
        "cens",
        o["censored"],
        "| fixed",
        round(f["lifetime"], 1),
        "| gap",
        round(1 - f["lifetime"] / o["lifetime"], 3),
        flush=True,
    )
    out.append(row)
write_json(run_dir / "env_sweep_extra.json", out)
print("DONE", run_dir)
