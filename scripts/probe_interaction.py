"""Interaction of the two pathways after calibration (decision D26, exploratory).

Slice: sugar 0.6 x looming 0..1 (11 levels) x 20 repeats, full 500 ms trials, calibrated
encoding (configs/encoding.yaml), decoder of decision D25. Run on the real connectome and on 20
degree- and sign-preserving shuffles. Every graph sees the same input spike schedules (same
trial seeds). Writes runs/<ts>_probe-interaction/ and reports/probe_interaction_trials.csv.
"""

from __future__ import annotations

import csv
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

SUGAR = 0.6
LEVELS = [round(float(x), 1) for x in np.linspace(0, 1, 11)]
REPS = 20
SEED = 7_100_000
SHUFFLES = list(range(1, 21))


def run_graph(shuffle_seed: int | None) -> list[dict]:
    from flight_or_bite.lif.circuits import load_circuits, resolve
    from flight_or_bite.lif.data import load_manifest
    from flight_or_bite.lif.decoder import decode
    from flight_or_bite.lif.encoding import load_encoding
    from flight_or_bite.lif.event_backend import EventBackend
    from flight_or_bite.lif.graph import load_connectome
    from flight_or_bite.lif.params import load_params
    from flight_or_bite.lif.shuffle import shuffled
    from flight_or_bite.types import Observation

    params, enc = load_params(), load_encoding()
    con = load_connectome(load_manifest(Path("configs/data.yaml")), params.connectome_version, Path("data"))
    c = load_circuits()
    sets = {"sugar": resolve(con, c["sugar_grn_right"]),
            "looming": np.concatenate([resolve(con, c["lplc2"]), resolve(con, c["lc4"])])}  # fmt: skip
    mn9, dnp01 = int(resolve(con, c["mn9"])[0]), resolve(con, c["dnp01"])
    graph = con if shuffle_seed is None else shuffled(con, shuffle_seed)
    backend = EventBackend(graph, params)
    rows = []
    for li, looming in enumerate(LEVELS):
        for rep in range(REPS):
            obs = Observation(sugar=SUGAR, bitter=0.0, looming=looming, hunger=0.0)
            r = backend.run_trial(enc.stimulus(obs, sets), enc.t_sim_ms, seed=SEED + li * REPS + rep)
            d = decode(
                r,
                mn9,
                dnp01,
                theta_eat_hz=enc.theta_eat_hz,
                eat_window_ms=enc.eat_window_ms,
                t_sim_ms=enc.t_sim_ms,
            )
            mn9_t = r.times_of(mn9)
            rows.append({
                "graph": "real" if shuffle_seed is None else f"shuffle_{shuffle_seed:02d}", "sugar": SUGAR,
                "looming": looming, "rep": rep, "action": d.action.value, "t_sim_ms": round(d.t_sim_ms, 1),
                "t_eat_ms": d.t_eat_ms, "t_escape_ms": d.t_escape_ms, "tie": d.tie,
                "t_first_mn9_ms": float(mn9_t[0]) if mn9_t.size else None, "mn9_rate_hz": round(r.rate_hz(mn9), 2),
                "dnp01_spikes": int(np.isin(r.spike_i, dnp01).sum()), "network_spikes": int(r.spike_i.size),
                "active_neurons": int(np.unique(r.spike_i).size),
            })  # fmt: skip
    print("done", rows[0]["graph"], flush=True)
    return rows


if __name__ == "__main__":
    from flight_or_bite.lif.encoding import load_encoding
    from flight_or_bite.runlog import start_run, write_json

    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run_dir = start_run("probe-interaction", {"sugar": SUGAR, "levels": LEVELS, "reps": REPS,
                                              "shuffles": SHUFFLES, "encoding": load_encoding().model_dump()},
                        seeds={"trial_seed_base": SEED, "shuffle_seeds": SHUFFLES})  # fmt: skip
    real = run_graph(None)
    with mp.get_context("spawn").Pool(workers) as pool:
        shuffled_rows = [row for rows in pool.map(run_graph, SHUFFLES) for row in rows]
    write_json(run_dir / "trials.json", {"real": real, "shuffled": shuffled_rows, "run_dir": str(run_dir)})
    with Path("reports/probe_interaction_trials.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(real[0]))
        w.writeheader()
        w.writerows(real + shuffled_rows)
    print("DONE", run_dir, flush=True)
