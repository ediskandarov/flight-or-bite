"""Exploratory probe of the looming channel (decision D18). Nothing here is tuned.

Looming drive: Poisson input to every LPLC2 and LC4 neuron of both sides at looming * R_max,
the encoding SPEC §4.1 describes. Sugar drive: the project's sugar GRN set at sugar * R_max.
All trials run the full window (no early stopping) so both read-outs are observed.
Writes runs/<ts>_probe-looming/probe.json and reports/probe_looming_trials.csv.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from flight_or_bite.lif.backend import Stimulus
from flight_or_bite.lif.backends import make_backend
from flight_or_bite.lif.circuits import load_circuits, resolve
from flight_or_bite.lif.data import load_manifest
from flight_or_bite.lif.graph import load_connectome
from flight_or_bite.lif.params import load_params
from flight_or_bite.runlog import start_run, write_json

LEVELS = np.round(np.linspace(0.0, 1.0, 11), 2)
SEED_DOSE, SEED_SETS, SEED_CONFLICT = 5_000_000, 6_000_000, 7_000_000
SUGAR_CONFLICT = 0.6

params = load_params()
enc = yaml.safe_load(Path("configs/encoding.yaml").read_text())
R_MAX, T_MS = float(enc["r_max_hz"]), float(enc["t_sim_ms"])
manifest = load_manifest(Path("configs/data.yaml"))
con = load_connectome(manifest, params.connectome_version, Path("data"))
circuits = load_circuits()
sugar_n = resolve(con, circuits["sugar_grn_right"])
loom_n = np.concatenate([resolve(con, circuits["lplc2"]), resolve(con, circuits["lc4"])])
mn9 = int(resolve(con, circuits["mn9"])[0])
dnp01 = resolve(con, circuits["dnp01"])  # order as in circuits.yaml: left, right
dn_side = ["left", "right"]
backend = make_backend("event", con, params)
run_dir = start_run(
    "probe-looming",
    {"lif": params.model_dump(), "encoding": enc, "levels": LEVELS.tolist(),
     "n_looming_neurons": int(len(loom_n)), "n_sugar_neurons": int(len(sugar_n)),
     "sugar_conflict": SUGAR_CONFLICT, "backend": "event", "early_stop": False},
    seeds={"dose": SEED_DOSE, "sets": SEED_SETS, "conflict": SEED_CONFLICT},
)  # fmt: skip


def stimulus(sugar: float, looming: float) -> Stimulus:
    neurons = np.concatenate([sugar_n, loom_n])
    rates = np.concatenate(
        [np.full(len(sugar_n), sugar * R_MAX), np.full(len(loom_n), looming * R_MAX)]
    )
    return Stimulus(neurons.astype(np.int32), rates)


def first(result, neuron: int) -> float | None:
    t = result.times_of(neuron)
    return float(t[0]) if t.size else None


def med(xs: list[float | None]) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(float(np.median(xs)), 1) if xs else None


def span(xs: list[float | None]) -> list[float] | None:
    xs = [x for x in xs if x is not None]
    return [round(min(xs), 1), round(max(xs), 1)] if xs else None


# ---- 3. looming -> DNp01 dose curve -------------------------------------------------------
dose = []
for li, level in enumerate(LEVELS):
    rows = []
    for rep in range(10):
        r = backend.run_trial(stimulus(0.0, float(level)), T_MS, seed=SEED_DOSE + li * 10 + rep)
        rows.append({
            "dn": [first(r, int(d)) for d in dnp01], "dn_rate": [r.rate_hz(int(d)) for d in dnp01],
            "mn9": first(r, mn9), "mn9_rate": r.rate_hz(mn9), "spikes": int(r.spike_i.size),
            "active": int(np.unique(r.spike_i).size), "wall_s": r.t_wall_ns / 1e9,
            "input_rate": float(np.isin(r.spike_i, loom_n).sum() / len(loom_n) / (T_MS / 1e3)),
        })  # fmt: skip
    any_dn = [min((t for t in x["dn"] if t is not None), default=None) for x in rows]
    dose.append({
        "looming": float(level), "drive_hz": float(level * R_MAX),
        "input_rate_hz_mean": round(float(np.mean([x["input_rate"] for x in rows])), 1),
        "p_dnp01_any_spike": sum(t is not None for t in any_dn) / len(rows),
        "p_spike_by_side": {s: sum(x["dn"][k] is not None for x in rows) / len(rows) for k, s in enumerate(dn_side)},
        "first_dnp01_t_sim_ms_p50": med(any_dn), "first_dnp01_t_sim_ms_range": span(any_dn),
        "dnp01_rate_hz_mean_by_side": {s: round(float(np.mean([x["dn_rate"][k] for x in rows])), 2) for k, s in enumerate(dn_side)},
        "p_mn9_any_spike": sum(x["mn9"] is not None for x in rows) / len(rows),
        "mn9_rate_hz_mean": round(float(np.mean([x["mn9_rate"] for x in rows])), 2),
        "network_spikes_mean": round(float(np.mean([x["spikes"] for x in rows])), 1),
        "active_neurons_mean": round(float(np.mean([x["active"] for x in rows])), 1),
        "wall_s_per_trial_mean": round(float(np.mean([x["wall_s"] for x in rows])), 3),
    })  # fmt: skip
    print(
        "dose",
        dose[-1]["looming"],
        dose[-1]["p_dnp01_any_spike"],
        dose[-1]["first_dnp01_t_sim_ms_p50"],
        dose[-1]["active_neurons_mean"],
        flush=True,
    )

# ---- 4. active sets and cross-pathway synapses --------------------------------------------
edges = pd.DataFrame({"pre": con.pre(), "post": con.post, "count": con.count})


def active_set(sugar: float, looming: float, seed0: int) -> tuple[set[int], set[int]]:
    """Neurons spiking in >= 1 of 10 trials, and in >= 5 of 10."""
    hits = np.zeros(con.n_neurons, dtype=np.int32)
    for rep in range(10):
        r = backend.run_trial(stimulus(sugar, looming), T_MS, seed=seed0 + rep)
        hits[np.unique(r.spike_i)] += 1
    return set(np.flatnonzero(hits >= 1).tolist()), set(np.flatnonzero(hits >= 5).tolist())


def synapses(sources: set[int], targets: set[int]) -> dict:
    sub = edges[edges.pre.isin(sources) & edges.post.isin(targets)]
    exc, inh = sub[sub["count"] > 0], sub[sub["count"] < 0]
    return {"edges": int(len(sub)), "excitatory_edges": int(len(exc)), "excitatory_synapses": int(exc["count"].sum()),
            "inhibitory_edges": int(len(inh)), "inhibitory_synapses": int(-inh["count"].sum()),
            "distinct_sources": int(sub.pre.nunique()), "distinct_targets": int(sub.post.nunique())}  # fmt: skip


dn_set, mn9_set = set(int(d) for d in dnp01), {mn9}
dn_inputs = set(edges[edges.post.isin(dn_set)].pre.tolist())
mn9_inputs = set(edges[edges.post == mn9].pre.tolist())
sets = {}
for level in (1.0, SUGAR_CONFLICT):
    k = int(level * 100)
    s_any, s_half = active_set(level, 0.0, SEED_SETS + k)
    l_any, l_half = active_set(0.0, level, SEED_SETS + 1000 + k)
    s_down, l_down = s_any - set(sugar_n.tolist()), l_any - set(loom_n.tolist())
    sets[f"level_{level}"] = {
        "sugar_active_any": len(s_any), "sugar_active_ge5": len(s_half), "sugar_active_excluding_stimulated": len(s_down),
        "looming_active_any": len(l_any), "looming_active_ge5": len(l_half), "looming_active_excluding_stimulated": len(l_down),
        "intersection_any": len(s_any & l_any), "intersection_ge5": len(s_half & l_half),
        "union_any": len(s_any | l_any),
        "sugar_active_contains_dnp01": sorted(int(x) for x in s_any & dn_set), "looming_active_contains_mn9": mn9 in l_any,
        "looming_active_contains_dnp01": sorted(int(x) for x in l_any & dn_set), "sugar_active_contains_mn9": mn9 in s_any,
        "n_dnp01_inputs": len(dn_inputs), "n_mn9_inputs": len(mn9_inputs),
        "sugar_active_that_are_dnp01_inputs": len(s_any & dn_inputs), "looming_active_that_are_mn9_inputs": len(l_any & mn9_inputs),
        "sugar_active_to_dnp01_direct": synapses(s_any, dn_set), "sugar_active_to_dnp01_inputs": synapses(s_any, dn_inputs),
        "looming_active_to_mn9_direct": synapses(l_any, mn9_set), "looming_active_to_mn9_inputs": synapses(l_any, mn9_inputs),
        "looming_active_to_dnp01_direct": synapses(l_any, dn_set), "sugar_active_to_mn9_direct": synapses(s_any, mn9_set),
    }  # fmt: skip
    print("sets", level, len(s_any), len(l_any), len(s_any & l_any), flush=True)

stim_to_dn = {"lplc2_lc4_to_dnp01_direct": synapses(set(loom_n.tolist()), dn_set),
              "sugar_grn_to_mn9_direct": synapses(set(sugar_n.tolist()), mn9_set)}  # fmt: skip

# ---- 5. conflict slice: sugar 0.6 x looming x 20 -------------------------------------------
trials = []
for li, level in enumerate(LEVELS):
    for rep in range(20):
        seed = SEED_CONFLICT + li * 20 + rep
        r = backend.run_trial(stimulus(SUGAR_CONFLICT, float(level)), T_MS, seed=seed)
        dn_t = [first(r, int(d)) for d in dnp01]
        trials.append({"sugar": SUGAR_CONFLICT, "looming": float(level), "rep": rep, "seed": seed,
                       "t_first_mn9_ms": first(r, mn9), "t_first_dnp01_left_ms": dn_t[0], "t_first_dnp01_right_ms": dn_t[1],
                       "mn9_rate_hz": round(r.rate_hz(mn9), 2), "dnp01_left_rate_hz": round(r.rate_hz(int(dnp01[0])), 2),
                       "dnp01_right_rate_hz": round(r.rate_hz(int(dnp01[1])), 2), "network_spikes": int(r.spike_i.size),
                       "active_neurons": int(np.unique(r.spike_i).size)})  # fmt: skip
    print("conflict", float(level), flush=True)

csv_path = Path("reports/probe_looming_trials.csv")
with csv_path.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(trials[0]))
    writer.writeheader()
    writer.writerows(trials)

write_json(run_dir / "probe.json", {
    "connectome_version": con.version, "r_max_hz": R_MAX, "t_sim_ms": T_MS,
    "n_lplc2": len(circuits["lplc2"].ids), "n_lc4": len(circuits["lc4"].ids), "n_looming_neurons": int(len(loom_n)),
    "n_sugar_neurons": int(len(sugar_n)), "dnp01_indices": [int(d) for d in dnp01], "dose": dose, "sets": sets,
    "stimulated_to_readout": stim_to_dn, "conflict_trials": trials, "run_dir": str(run_dir),
})  # fmt: skip
print("DONE", run_dir, flush=True)
