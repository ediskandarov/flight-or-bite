"""Exploratory probe R5 (decision D35): does co-stimulation suppress DNp01, and how?

PROTOCOL — written and committed BEFORE the first run. Nothing is tuned afterwards.

Common to all parts
  Connectome v783, event backend, full 500 ms trials, calibrated encoding (configs/encoding.yaml),
  hunger = 0 (so alpha has no effect and the sugar drive equals the calibrated one).
  Outcome per trial: did either DNp01 spike at least once (yes / no); also the time of its first
  spike. looming in {0.6, 0.8, 1.0}; 40 repeats per cell; trial seeds 7_500_000 + repeat.
  PAIRING: each channel draws its Poisson kicks from its own RNG stream keyed by (seed, channel),
  so for one seed the looming input is bit-identical in every condition. The control is
  looming-only on the same seeds.
  PRE-SPECIFIED TEST: exact two-sided McNemar test on the paired yes/no outcomes, condition vs
  control, separately for each looming level (primary). The same test pooled over the three
  levels (120 pairs) is reported as supplementary. "Suppression" = discordant pairs in which the
  control spiked and the condition did not (b) outnumber the opposite (c).

A. Specificity. Co-stimulus at the rate sugar 0.6 would give (0.6 * r_max_sugar_hz):
   (0) the project's sugar GRNs (reference), (1) the 20 bitter GRNs of the authors' list,
   (2) 20 random sensory neurons that are not gustatory: FlyWire annotation super_class ==
   'sensory' and cell_class != 'gustatory', drawn without replacement with
   numpy.random.default_rng(1). Sets drawn with seeds 2..5 are supplementary.
B. Dose. Sugar GRNs at sugar in {0, 0.3, 0.6, 1.0}; McNemar of each non-zero dose vs sugar 0.
C. Mediators. S = neurons that spike in at least one of 40 sugar-only trials (sugar 0.6).
   P = presynaptic partners of either DNp01; P_loom = those of P that spike in at least one
   looming-only trial (any of the three levels). Candidates:
     M_all  = inhibitory neurons of S with at least one edge onto P or onto DNp01;
     M_loom = inhibitory neurons of S with at least one edge onto P_loom or onto DNp01.
   Each set is silenced (all outgoing weights zero, as `silence` in model.py) in BOTH the control
   and the sugar 0.6 condition; McNemar as above. Types are read from the annotation table.
D. Alternative looming encoding: level = fraction of LPLC2 + LC4. On each trial
   x = looming * f_max * 314 neurons are driven at 100 Hz: k = floor(x) + Bernoulli(x - floor(x)),
   the subset drawn uniformly at random from the 314 with the (seed, "subset") stream; the rest
   receive nothing. f_max is calibrated like the rate code: bisection to P(ESCAPE) = 0.5 at
   looming 0.5, 50 trials per step on dev seeds 0..49, tolerance 0.002 on f_max, then checked on
   dev seeds 500..549. Part B is repeated under this encoding; t_sim of the first DNp01 spike
   is reported.
"""

from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from flight_or_bite.lif.backend import Stimulus
from flight_or_bite.lif.circuits import load_circuits, resolve
from flight_or_bite.lif.data import load_manifest
from flight_or_bite.lif.decoder import decode
from flight_or_bite.lif.encoding import load_encoding
from flight_or_bite.lif.event_backend import EventBackend
from flight_or_bite.lif.graph import load_connectome
from flight_or_bite.lif.params import load_params
from flight_or_bite.runlog import start_run, write_json
from flight_or_bite.types import Action

LOOMING = (0.6, 0.8, 1.0)
REPS, SEED = 40, 7_500_000
SMOKE = os.environ.get("R5_SMOKE") == "1"  # crash test only: 2 repeats on unrelated seeds
if SMOKE:
    REPS, SEED = 2, 1_234_000
ANNOT_COMMIT = "8587524c1748ce5ef2080822a2fc890fc03bf597"
ANNOT_BLOB = "afea3e15a5671f5da0b9f7dd2e932d328c3b57a0"
ANNOT_PATH = Path("data/flywire_annotations_783.tsv")
FRACTION_RATE_HZ = 100.0

params, enc = load_params(), load_encoding()
con = load_connectome(load_manifest(Path("configs/data.yaml")), params.connectome_version, Path("data"))
circ = load_circuits()
sugar_n, bitter_n = resolve(con, circ["sugar_grn_right"]), resolve(con, circ["bitter_grn_shiu"])
loom_n = np.concatenate([resolve(con, circ["lplc2"]), resolve(con, circ["lc4"])])
mn9, dnp01 = int(resolve(con, circ["mn9"])[0]), resolve(con, circ["dnp01"])
backend = EventBackend(con, params)
N_STEPS = round(enc.t_sim_ms / params.dt_ms)
CO_RATE = 0.6 * enc.r_max_sugar_hz


def annotations() -> pd.DataFrame:
    if not ANNOT_PATH.is_file():
        url = (f"https://raw.githubusercontent.com/flyconnectome/flywire_annotations/{ANNOT_COMMIT}/"
               "supplemental_files/Supplemental_file1_neuron_annotations.tsv")  # fmt: skip
        data = urllib.request.urlopen(url, timeout=300).read()  # noqa: S310
        if hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest() != ANNOT_BLOB:
            raise RuntimeError("annotation table does not match the pinned git blob")
        ANNOT_PATH.write_bytes(data)
    cols = ["root_id", "super_class", "cell_class", "cell_sub_class", "cell_type", "top_nt", "side"]
    return pd.read_csv(ANNOT_PATH, sep="\t", usecols=cols, low_memory=False)


def stream(seed: int, channel: str) -> np.random.Generator:
    return np.random.default_rng([seed, int.from_bytes(channel.encode(), "little") % (2**32)])


def kicks(neurons: np.ndarray, rate_hz: float, seed: int, channel: str) -> tuple[np.ndarray, np.ndarray]:
    """Bernoulli(rate * dt) per neuron and step from the channel's own stream."""
    p = rate_hz * params.dt_ms * 1e-3
    steps, cols = np.nonzero(stream(seed, channel).random((N_STEPS, len(neurons))) < p)
    return steps.astype(np.int64), neurons[cols].astype(np.int32)


def looming_kicks(level: float, seed: int, fraction: float | None):
    """(kicks, driven neurons). Only driven neurons lose their refractory period, as in model.py."""
    if fraction is None:  # rate code (calibrated)
        return kicks(loom_n, level * enc.r_max_looming_hz, seed, "looming"), loom_n
    x = level * fraction * len(loom_n)
    rng = stream(seed, "subset")
    k = int(np.floor(x)) + int(rng.random() < x - np.floor(x))
    subset = np.sort(rng.choice(loom_n, size=k, replace=False)) if k else loom_n[:0]
    return kicks(subset, FRACTION_RATE_HZ, seed, "looming"), subset


def trial(level: float, seed: int, co: np.ndarray | None = None, co_rate: float = 0.0, *,
          silenced: np.ndarray | None = None, fraction: float | None = None, want_active: bool = False) -> dict:  # fmt: skip
    loom_kicks, driven = looming_kicks(level, seed, fraction)
    parts = [loom_kicks]
    stimulated = [driven]
    if co is not None and co_rate > 0:
        parts.append(kicks(co, co_rate, seed, "co"))
        stimulated.append(co)
    steps = np.concatenate([p[0] for p in parts])
    neurons = np.concatenate([p[1] for p in parts])
    order = np.argsort(steps, kind="stable")
    stim = Stimulus(np.concatenate(stimulated).astype(np.int32), np.zeros(sum(len(s) for s in stimulated)))
    r = backend.run_trial(stim, enc.t_sim_ms, seed=seed, silenced=silenced, kicks=(steps[order], neurons[order]))
    d = decode(
        r,
        mn9,
        dnp01,
        theta_eat_hz=enc.theta_eat_hz,
        eat_window_ms=enc.eat_window_ms,
        t_sim_ms=enc.t_sim_ms,
    )
    out = {"dn": d.t_escape_ms is not None, "t_dn": d.t_escape_ms, "action": d.action.value,
           "mn9_rate": r.rate_hz(mn9)}  # fmt: skip
    if want_active:
        out["active"] = np.unique(r.spike_i)
    return out


def cell(level: float, co=None, co_rate=0.0, **kw) -> list[dict]:
    return [trial(level, SEED + rep, co, co_rate, **kw) for rep in range(REPS)]


def mcnemar(control: list[dict], cond: list[dict]) -> dict:
    b = sum(c["dn"] and not x["dn"] for c, x in zip(control, cond, strict=True))
    c_ = sum(not c["dn"] and x["dn"] for c, x in zip(control, cond, strict=True))
    p = binomtest(b, b + c_, 0.5).pvalue if b + c_ else 1.0
    t = [x["t_dn"] for x in cond if x["t_dn"] is not None]
    return {"control_yes": sum(c["dn"] for c in control), "condition_yes": sum(x["dn"] for x in cond),
            "n": len(cond), "b_control_only": b, "c_condition_only": c_, "p_mcnemar_exact": float(p),
            "t_dn_ms_p50": float(np.median(t)) if t else None,
            "mn9_rate_hz": float(np.mean([x["mn9_rate"] for x in cond]))}  # fmt: skip


def compare(control: dict, run_condition) -> dict:
    per, pooled_c, pooled_x = {}, [], []
    for level in LOOMING:
        rows = run_condition(level)
        per[str(level)] = mcnemar(control[level], rows)
        pooled_c += control[level]
        pooled_x += rows
    per["pooled"] = mcnemar(pooled_c, pooled_x)
    return per


if __name__ == "__main__":
    run_dir = start_run("probe-r5", {"encoding": enc.model_dump(), "looming": LOOMING, "reps": REPS,
                                     "co_rate_hz": CO_RATE, "fraction_rate_hz": FRACTION_RATE_HZ},
                        seeds={"trial_seed_base": SEED})  # fmt: skip
    out: dict = {"run_dir": str(run_dir), "co_rate_hz": CO_RATE}
    ann = annotations()
    index_of = {int(r): i for i, r in enumerate(con.ids)}

    control = {lv: [trial(lv, SEED + rep, want_active=True) for rep in range(REPS)] for lv in LOOMING}
    out["control"] = {str(lv): {"yes": sum(r["dn"] for r in rows), "n": REPS,
                                "t_dn_ms_p50": float(np.median([r["t_dn"] for r in rows if r["dn"]])) if any(r["dn"] for r in rows) else None}
                      for lv, rows in control.items()}  # fmt: skip
    print("control", out["control"], flush=True)

    # ---- A. specificity ------------------------------------------------------------------
    pool = ann[(ann.super_class == "sensory") & (ann.cell_class != "gustatory") & ann.root_id.isin(index_of)]
    out["A"] = {
        "sensory_pool": int(len(pool)),
        "sensory_pool_classes": pool.cell_class.value_counts(dropna=False).head(12).to_dict(),
    }
    conditions = {"sugar_grn": sugar_n, "bitter_grn": bitter_n}
    for s in range(1, 6):
        picked = pool.sample(n=20, random_state=np.random.default_rng(s))
        conditions[f"random_sensory_{s}"] = np.array([index_of[int(r)] for r in picked.root_id], dtype=np.int32)
        out["A"][f"random_sensory_{s}_classes"] = picked.cell_class.value_counts(dropna=False).to_dict()
    for name, neurons in conditions.items():
        out["A"][name] = compare(control, lambda lv, n=neurons: cell(lv, n, CO_RATE))
        print("A", name, out["A"][name]["pooled"], flush=True)

    # ---- B. dose -------------------------------------------------------------------------
    out["B"] = {}
    for sugar in (0.3, 0.6, 1.0):
        out["B"][str(sugar)] = compare(control, lambda lv, s=sugar: cell(lv, sugar_n, s * enc.r_max_sugar_hz))
        print("B", sugar, out["B"][str(sugar)]["pooled"], flush=True)

    # ---- C. mediators --------------------------------------------------------------------
    sugar_active: set[int] = set()
    for rep in range(REPS):
        stim = Stimulus(sugar_n.astype(np.int32), np.zeros(len(sugar_n)))
        r = backend.run_trial(stim, enc.t_sim_ms, seed=SEED + rep, kicks=kicks(sugar_n, CO_RATE, SEED + rep, "co"))
        sugar_active |= set(np.unique(r.spike_i).tolist())
    loom_active = set(np.concatenate([r["active"] for rows in control.values() for r in rows]).tolist())
    pre, post, count = con.pre(), con.post, con.count
    dn_set = set(int(d) for d in dnp01)
    partners = set(pre[np.isin(post, dnp01)].tolist())
    partners_loom = partners & loom_active
    inhibitory = {int(i) for i in sugar_active if (seg := count[con.indptr[i] : con.indptr[i + 1]]).size and seg[0] < 0}

    def onto(targets: set[int]) -> dict[int, int]:
        mask = np.isin(pre, list(inhibitory)) & np.isin(post, list(targets))
        return pd.Series(-count[mask]).groupby(pre[mask]).sum().to_dict()

    m_all, m_loom = onto(partners | dn_set), onto(partners_loom | dn_set)
    out["C"] = {"n_sugar_active": len(sugar_active), "n_sugar_active_inhibitory": len(inhibitory),
                "n_dnp01_partners": len(partners), "n_dnp01_partners_loom_active": len(partners_loom),
                "n_M_all": len(m_all), "n_M_loom": len(m_loom)}  # fmt: skip
    for label, members in (("M_all", m_all), ("M_loom", m_loom)):
        idx = np.array(sorted(members), dtype=np.int32)
        ctrl_s = {lv: cell(lv, silenced=idx) for lv in LOOMING}
        out["C"][label] = {"silenced_control_yes": {str(lv): sum(r["dn"] for r in rows) for lv, rows in ctrl_s.items()},
                           "test": compare(ctrl_s, lambda lv, i=idx: cell(lv, sugar_n, CO_RATE, silenced=i))}  # fmt: skip
        print("C", label, len(idx), out["C"][label]["test"]["pooled"], flush=True)
    meta = ann.drop_duplicates("root_id").set_index("root_id")
    direct = onto(dn_set)
    out["C"]["members"] = [
        {"root_id": int(con.ids[i]), "synapses_onto_loom_active_partners_or_dnp01": int(w),
         "synapses_onto_all_partners_or_dnp01": int(m_all.get(i, 0)), "synapses_onto_dnp01_direct": int(direct.get(i, 0)),
         **({k: (None if pd.isna(v) else v) for k, v in meta.loc[int(con.ids[i])].to_dict().items()}
            if int(con.ids[i]) in meta.index else {"cell_type": None, "note": "not in the annotation table"})}
        for i, w in sorted(m_loom.items(), key=lambda kv: -kv[1])
    ]  # fmt: skip

    # ---- D. fraction code ----------------------------------------------------------------
    def p_escape(fraction: float, seeds) -> float:
        hits = 0
        for s in seeds:
            hits += trial(0.5, s, fraction=fraction)["action"] == Action.ESCAPE.value
        return hits / len(seeds)

    lo, hi, steps = 0.0, 1.0, []
    while hi - lo >= (0.2 if SMOKE else 0.002):
        mid = 0.5 * (lo + hi)
        p = p_escape(mid, range(3 if SMOKE else 50))
        steps.append({"f_max": mid, "neurons_at_0.5": 0.5 * mid * len(loom_n), "p": p})
        print("D bisect", steps[-1], flush=True)
        lo, hi = (mid, hi) if p < 0.5 else (lo, mid)
    f_max = hi
    out["D"] = {"f_max": f_max, "neurons_at_level_1": f_max * len(loom_n), "steps": steps,
                "check_p_escape_at_0.5": p_escape(f_max, range(500, 503 if SMOKE else 550)), "curve": []}  # fmt: skip
    for lv in np.round(np.linspace(0, 1, 11), 1):
        rows = [trial(float(lv), s, fraction=f_max) for s in range(500, 503 if SMOKE else 550)]
        t = [r["t_dn"] for r in rows if r["dn"]]
        out["D"]["curve"].append({"looming": float(lv), "neurons": float(lv * f_max * len(loom_n)), "p_dnp01": float(np.mean([r["dn"] for r in rows])),
                                  "t_dn_ms_p50": float(np.median(t)) if t else None, "t_dn_ms_range": [float(min(t)), float(max(t))] if t else None})  # fmt: skip
    control_f = {lv: cell(lv, fraction=f_max) for lv in LOOMING}
    out["D"]["control"] = {str(lv): {"yes": sum(r["dn"] for r in rows), "t_dn_ms_p50": float(np.median([r["t_dn"] for r in rows if r["dn"]])) if any(r["dn"] for r in rows) else None}
                           for lv, rows in control_f.items()}  # fmt: skip
    out["D"]["dose"] = {}
    for sugar in (0.3, 0.6, 1.0):
        out["D"]["dose"][str(sugar)] = compare(
            control_f, lambda lv, s=sugar: cell(lv, sugar_n, s * enc.r_max_sugar_hz, fraction=f_max)
        )
        print("D", sugar, out["D"]["dose"][str(sugar)]["pooled"], flush=True)

    write_json(run_dir / "probe_r5.json", out)
    print("DONE", run_dir, flush=True)
    sys.exit(0)
