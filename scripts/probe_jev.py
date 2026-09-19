"""Exploratory probe of Jev with the draft v0 prompts. Nothing is tuned; templates were committed
before this script was first run (713fe97).

Slice: sugar 0.6, bitter 0.05, hunger 0.5 (the background of the connectome's conflict slice),
looming 0.0 .. 1.0 in 11 levels, all three state modes. 20 repeats at looming 0.2 / 0.5 / 0.8 (to
measure the spread over identical requests), 5 repeats elsewhere. Raw exchanges are logged by
JevClient to runs/jev_raw/. Writes runs/<ts>_probe-jev/probe.json.
"""

from __future__ import annotations

import numpy as np
from dotenv import find_dotenv, load_dotenv

from flight_or_bite.arbiters.jev_arbiter import MODES, JevArbiter, load_prompt, prompt_hash
from flight_or_bite.arbiters.jev_client import MODEL, JevClient, build_payload
from flight_or_bite.runlog import start_run, write_json
from flight_or_bite.types import Observation

SUGAR, BITTER, HUNGER = 0.6, 0.05, 0.5
LEVELS = [round(x, 1) for x in np.linspace(0.0, 1.0, 11)]
DENSE = {0.2: 20, 0.5: 20, 0.8: 20}
DEFAULT_REPS = 5
MAX_CALLS = 400

load_dotenv(find_dotenv(usecwd=True))
run_dir = start_run("probe-jev", {"sugar": SUGAR, "bitter": BITTER, "hunger": HUNGER,
                                  "levels": LEVELS, "dense": DENSE, "default_reps": DEFAULT_REPS,
                                  "model": MODEL, "prompt_hashes": {m: prompt_hash(m) for m in MODES}})  # fmt: skip
client = JevClient(max_calls=MAX_CALLS)
rng = np.random.default_rng(0)
records, requests = [], {}
try:
    for mode in MODES:
        prompt = load_prompt(mode)
        arbiter = JevArbiter(client, prompt)
        for looming in LEVELS:
            obs = Observation(sugar=SUGAR, bitter=BITTER, looming=looming, hunger=HUNGER)
            if looming in DENSE:  # keep the exact request bodies of the three dense points
                body = build_payload(prompt.state(obs), {"action": prompt.question()}, MODEL)
                requests[f"{mode}@{looming}"] = body.decode()
            for rep in range(DENSE.get(looming, DEFAULT_REPS)):
                d = arbiter.decide(obs, rng)
                records.append({"mode": mode, "looming": looming, "rep": rep,
                                "probs": {a.value: p for a, p in d.probs.items()},
                                "t_wall_ms": d.t_wall_ns / 1e6, "model": d.meta["model_version"],
                                "generation_id": d.meta["generation_id"],
                                "cost_usd": d.meta["cost_usd"]})  # fmt: skip
        print(mode, "done; calls so far:", client.budget.used, flush=True)
finally:
    client.close()
    write_json(run_dir / "probe.json", {"records": records, "requests": requests,
                                        "calls": client.budget.used, "run_dir": str(run_dir)})  # fmt: skip
print("DONE", run_dir, flush=True)
