"""Choose Jev's main state mode on dev (decision D49, rule in PREREG.md §2).

The four modes play the same 50 dev episodes (seeds 0-49) online, with the native action (the
response's `choice`). Main mode = highest mean lifetime; ties go to the mode with fewer calls.
Modes run one after another over one keep-alive session each. Decisions that needed a retry are
excluded from the latency figures. Raw exchanges are logged by JevClient to runs/jev_raw/.
"""

from __future__ import annotations

import sys
from collections import Counter

import numpy as np
from dotenv import find_dotenv, load_dotenv

from flight_or_bite.arbiters.jev_arbiter import MODES, JevArbiter, load_prompt, prompt_hash
from flight_or_bite.arbiters.jev_client import JevClient
from flight_or_bite.arena.env import Arena, load_env_config
from flight_or_bite.eval.episodes import arbiter_rng
from flight_or_bite.eval.stats import bootstrap_mean_ci
from flight_or_bite.runlog import start_run, write_json
from flight_or_bite.types import Action

SEEDS = range(50)
load_dotenv(find_dotenv(usecwd=True))
cfg = load_env_config()
modes = sys.argv[1:] or list(MODES)
run_dir = start_run("select-jev-mode", {"modes": modes, "env": cfg.model_dump(),
                                         "prompt_hashes": {m: prompt_hash(m) for m in modes}},
                    seeds={"dev": [SEEDS[0], SEEDS[-1]]})  # fmt: skip
out = {}
for mode in modes:
    client = JevClient()
    arbiter = JevArbiter(client, load_prompt(mode), retries=5)
    arena = Arena(cfg)
    episodes, walls, models = [], [], Counter()
    try:
        for seed in SEEDS:
            obs, rng = arena.reset(seed), arbiter_rng(seed, arbiter.name)
            done, info, counts = False, {}, Counter()
            while not done:
                d = arbiter.decide(obs, rng)
                if not d.meta["retried"]:
                    walls.append(d.t_wall_ns / 1e6)
                models[d.meta["model_version"]] += 1
                obs, done, info = arena.step(d.action)
                counts[info["action"].value] += 1
            episodes.append({"seed": seed, "lifetime": info["lifetime"], "cause": info["cause"],
                             "energy": info["energy"], "actions": dict(counts)})  # fmt: skip
            print(mode, seed, info["lifetime"], info["cause"], flush=True)
    finally:
        client.close()
    life = np.array([e["lifetime"] for e in episodes], dtype=float)
    lo, hi = (
        bootstrap_mean_ci(life, np.random.default_rng(1)) if len(life) > 1 else (float("nan"),) * 2
    )
    acts = Counter()
    for e in episodes:
        acts.update(e["actions"])
    n_act = sum(acts.values())
    out[mode] = {"episodes": episodes, "lifetime_mean": float(life.mean()), "ci95": [lo, hi],
                 "lifetime_median": float(np.median(life)), "calls": client.budget.session,
                 "causes": dict(Counter(e["cause"] for e in episodes)),
                 "action_share": {a.value: acts[a.value] / n_act for a in Action},
                 "t_wall_ms": {"n": len(walls), "p50": float(np.percentile(walls, 50)), "p95": float(np.percentile(walls, 95))},
                 "models": dict(models)}  # fmt: skip
    write_json(run_dir / "selection.json", out)
    print(
        "MODE",
        mode,
        out[mode]["lifetime_mean"],
        out[mode]["ci95"],
        out[mode]["calls"],
        out[mode]["t_wall_ms"],
        flush=True,
    )
print("DONE", run_dir, flush=True)
