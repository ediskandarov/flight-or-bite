"""Formal validity gates G1-G7 (SPEC §5). Protocol: configs/gates.yaml, fixed before the run."""

from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy.stats import spearmanr

from flight_or_bite.eval.stats import holm, mcnemar_exact
from flight_or_bite.lif.encoding import load_encoding
from flight_or_bite.lif.params import load_params
from flight_or_bite.lif.shuffle import shuffled
from flight_or_bite.lif.trial import TrialRunner, load_real_connectome
from flight_or_bite.types import Action, Observation
from flight_or_bite.validation.gates import GateResult

EAT_WINDOW_S = 0.05


def load_cfg() -> dict[str, Any]:
    cfg = yaml.safe_load(Path("configs/gates.yaml").read_text())
    if os.environ.get("FOB_GATES_SMOKE") == "1":  # crash test: tiny, on unrelated seeds
        for g in ("G1", "G2", "G3", "G5", "G7"):
            cfg[g]["n_rep"] = 2
            cfg[g]["seed_base"] += 50_000_000
        cfg["G1"]["levels"] = cfg["G3"]["levels"] = 3
        cfg["G4"]["shuffle_seeds"] = [1, 2]
        cfg["G6"]["n_rep"] = {"G1": 2, "G2": 2, "G3": 2}
    return cfg


def make_runner(shuffle_seed: int | None = None, *, r_max_sugar_scale: float = 1.0,
                r_max_looming_scale: float = 1.0, w_syn_scale: float = 1.0, alpha: float | None = None,
                looming_fraction: float | None = None, **_: Any) -> TrialRunner:  # fmt: skip
    params, enc = load_params(), load_encoding()
    params = params.model_copy(update={"w_syn_mv": params.w_syn_mv * w_syn_scale})
    enc = enc.model_copy(update={
        "r_max_sugar_hz": enc.r_max_sugar_hz * r_max_sugar_scale,
        "r_max_bitter_hz": enc.r_max_bitter_hz * r_max_sugar_scale,  # tied to sugar (D25)
        "r_max_looming_hz": enc.r_max_looming_hz * r_max_looming_scale,
        "alpha": enc.alpha if alpha is None else alpha,
    })  # fmt: skip
    con = load_real_connectome(params)
    if shuffle_seed is not None:
        con = shuffled(con, shuffle_seed)
    return TrialRunner(con, params, enc, looming_fraction=looming_fraction)


def _rho(x, y) -> float:
    r = spearmanr(x, y).statistic
    return 0.0 if np.isnan(r) else float(r)


def g1_metric(runner: TrialRunner, cfg: dict, *, n_rep: int | None = None, seed_offset: int = 0,
              hunger: float = 0.0) -> dict:  # fmt: skip
    n_rep = n_rep or cfg["n_rep"]
    sugar = np.round(np.linspace(0, 1, cfg["levels"]), 3)
    rates = np.array([[runner.run(Observation(float(s), 0.0, 0.0, hunger), cfg["seed_base"] + seed_offset + li * n_rep + r).mn9_rate_hz
                       for r in range(n_rep)] for li, s in enumerate(sugar)])  # fmt: skip
    return {"metric": _rho(np.repeat(sugar, n_rep), rates.ravel()), "sugar": sugar.tolist(),
            "mn9_rate_hz_mean": rates.mean(axis=1).round(2).tolist(),
            "rho_over_level_means": _rho(sugar, rates.mean(axis=1)), "n_rep": n_rep}  # fmt: skip


def g2_metric(runner: TrialRunner, cfg: dict, *, n_rep: int | None = None, seed_offset: int = 0,
              hunger: float = 0.0, eat_spikes: int | None = None) -> dict:  # fmt: skip
    n_rep = n_rep or cfg["n_rep"]
    theta = None if eat_spikes is None else (eat_spikes - 0.5) / EAT_WINDOW_S
    p_eat, mn9 = [], []
    for bitter in cfg["bitter_levels"]:  # the same seeds at every bitter level: paired
        trials = [runner.run(Observation(cfg["sugar"], bitter, 0.0, hunger), cfg["seed_base"] + seed_offset + r,
                             theta_eat_hz=theta) for r in range(n_rep)]  # fmt: skip
        p_eat.append(float(np.mean([t.decoded.action is Action.EAT for t in trials])))
        mn9.append(float(np.mean([t.mn9_rate_hz for t in trials])))
    drop = 1.0 - p_eat[-1] / p_eat[0] if p_eat[0] > 0 else 0.0
    return {
        "metric": drop,
        "bitter": cfg["bitter_levels"],
        "p_eat": p_eat,
        "mn9_rate_hz_mean": mn9,
        "n_rep": n_rep,
    }


def g3_metric(runner: TrialRunner, cfg: dict, *, n_rep: int | None = None, seed_offset: int = 0) -> dict:
    n_rep = n_rep or cfg["n_rep"]
    looming = np.round(np.linspace(0, 1, cfg["levels"]), 3)
    p, t50 = [], []
    for li, lv in enumerate(looming):
        trials = [runner.run(Observation(0.0, 0.0, float(lv), 0.0), cfg["seed_base"] + seed_offset + li * n_rep + r)
                  for r in range(n_rep)]  # fmt: skip
        esc = [t.decoded.t_sim_ms for t in trials if t.decoded.action is Action.ESCAPE]
        p.append(len(esc) / n_rep)
        t50.append(float(np.median(esc)) if esc else None)
    return {"metric": _rho(looming, p), "looming": looming.tolist(), "p_escape": p,
            "t_sim_ms_p50": t50, "n_rep": n_rep}  # fmt: skip


def shuffle_worker(shuffle_seed: int) -> dict:
    cfg = load_cfg()
    runner = make_runner(shuffle_seed)
    return {"seed": shuffle_seed, "G1": g1_metric(runner, cfg["G1"])["metric"],
            "G2": g2_metric(runner, cfg["G2"])["metric"], "G3": g3_metric(runner, cfg["G3"])["metric"]}  # fmt: skip


def variant_worker(item: tuple[str, dict]) -> dict:
    name, spec = item
    cfg = load_cfg()
    g6 = cfg["G6"]
    runner = make_runner(**spec)
    off, hunger = g6["seed_base_offset"], spec.get("hunger", 0.0)
    out: dict[str, Any] = {"variant": name, "spec": spec}
    touches_sugar = any(k in spec for k in ("r_max_sugar_scale", "w_syn_scale", "alpha"))
    touches_looming = any(k in spec for k in ("r_max_looming_scale", "w_syn_scale", "looming_fraction"))
    if touches_sugar:
        out["G1"] = g1_metric(runner, cfg["G1"], n_rep=g6["n_rep"]["G1"], seed_offset=off, hunger=hunger)
    if touches_sugar or "eat_spikes" in spec:
        out["G2"] = g2_metric(runner, cfg["G2"], n_rep=g6["n_rep"]["G2"], seed_offset=off, hunger=hunger,
                              eat_spikes=spec.get("eat_spikes"))  # fmt: skip
    if touches_looming:
        out["G3"] = g3_metric(runner, cfg["G3"], n_rep=g6["n_rep"]["G3"], seed_offset=off)
    t = cfg
    out["passed"] = all([
        out.get("G1", {"metric": 1})["metric"] > t["G1"]["threshold"],
        out.get("G3", {"metric": 1})["metric"] > t["G3"]["threshold"],
        out.get("G2", {"metric": 1})["metric"] > 0,
    ])  # fmt: skip
    return out


def suppression(runner: TrialRunner, sugar: float, levels: list[float], n_rep: int, seed_base: int,
                ablated: np.ndarray | None = None) -> dict:  # fmt: skip
    """DNp01 spiked yes/no: looming-only vs sugar + looming on the same seeds (paired)."""
    per, pool_c, pool_x = {}, [], []
    for li, lv in enumerate(levels):
        seeds = [seed_base + li * n_rep + r for r in range(n_rep)]
        control = [runner.run(Observation(0.0, 0.0, lv, 0.0), s, ablated=ablated) for s in seeds]
        cond = [runner.run(Observation(sugar, 0.0, lv, 0.0), s, ablated=ablated) for s in seeds]
        c_yes, x_yes = [t.dnp01_spiked for t in control], [t.dnp01_spiked for t in cond]
        per[str(lv)] = mcnemar_exact(c_yes, x_yes) | {
            "decisions_control": {a.value: sum(t.decoded.action is a for t in control) for a in Action},
            "decisions_condition": {a.value: sum(t.decoded.action is a for t in cond) for a in Action},
        }
        pool_c += c_yes
        pool_x += x_yes
    pooled = mcnemar_exact(pool_c, pool_x)
    return {"levels": per, "pooled": pooled, "effect_b_minus_c": pooled["b"] - pooled["c"]}


def run_gate(name: str, workers: int = 5, log=print) -> GateResult:
    cfg = load_cfg()
    c = cfg[name]
    if name in ("G1", "G2", "G3"):
        r = {"G1": g1_metric, "G2": g2_metric, "G3": g3_metric}[name](make_runner(), c)
        return GateResult(name, bool(r["metric"] > c["threshold"]), r["metric"], c["threshold"], r)

    if name == "G4":
        real = make_runner()
        real_m = {"G1": g1_metric(real, cfg["G1"])["metric"], "G2": g2_metric(real, cfg["G2"])["metric"],
                  "G3": g3_metric(real, cfg["G3"])["metric"]}  # fmt: skip
        with mp.get_context("spawn").Pool(workers) as pool:
            nulls = pool.map(shuffle_worker, c["shuffle_seeds"])
        detail, ok = {}, []
        for g in ("G1", "G2", "G3"):
            null = [n[g] for n in nulls]
            cut = float(np.percentile(null, c["percentile"]))
            ok.append(real_m[g] > cut)
            detail[g] = {
                "real": real_m[g],
                "null": null,
                "null_percentile": cut,
                "null_max": max(null),
                "outside": ok[-1],
            }
        return GateResult(
            name,
            all(ok),
            float(sum(ok)),
            3.0,
            {"metric_is": "number of G1-G3 metrics outside the null", **detail},
        )

    if name == "G5":
        runner = make_runner()
        n, sb = c["n_rep"], c["seed_base"]
        esc = [
            runner.run(
                Observation(0.0, 0.0, c["dnp01"]["looming"], 0.0),
                sb + r,
                ablated=runner.named["dnp01"],
            )
            for r in range(n)
        ]
        esc0 = [runner.run(Observation(0.0, 0.0, c["dnp01"]["looming"], 0.0), sb + r) for r in range(n)]
        eat = [
            runner.run(
                Observation(c["mn9"]["sugar"], 0.0, 0.0, 0.0),
                sb + 1000 + r,
                ablated=runner.named["mn9"],
            )
            for r in range(n)
        ]
        eat0 = [runner.run(Observation(c["mn9"]["sugar"], 0.0, 0.0, 0.0), sb + 1000 + r) for r in range(n)]
        p = lambda ts, a: float(np.mean([t.decoded.action is a for t in ts]))  # noqa: E731
        m = c["m_loom"]
        intact = suppression(runner, m["sugar"], m["looming_levels"], n, sb + 2000)
        no_m = suppression(runner, m["sugar"], m["looming_levels"], n, sb + 2000, ablated=runner.named["m_loom"])
        no_cl20 = suppression(runner, m["sugar"], m["looming_levels"], n, sb + 2000, ablated=runner.named["cl20"])

        def retained(x: dict) -> float:
            whole = intact["effect_b_minus_c"]
            return x["effect_b_minus_c"] / whole if whole else float("nan")

        d = {"dnp01_ablated": {"p_escape": p(esc, Action.ESCAPE), "p_escape_intact": p(esc0, Action.ESCAPE), "max": c["dnp01"]["max_p_escape"]},
             "mn9_ablated": {"p_eat": p(eat, Action.EAT), "p_eat_intact": p(eat0, Action.EAT), "max": c["mn9"]["max_p_eat"]},
             "suppression_intact": intact, "m_loom_ablated": no_m | {"retained": retained(no_m), "max_retained": m["max_retained"]},
             "cl20_ablated": no_cl20 | {"retained": retained(no_cl20), "report_only": True}}  # fmt: skip
        ok = [d["dnp01_ablated"]["p_escape"] <= c["dnp01"]["max_p_escape"], d["mn9_ablated"]["p_eat"] <= c["mn9"]["max_p_eat"],
              intact["effect_b_minus_c"] > 0 and d["m_loom_ablated"]["retained"] <= m["max_retained"]]  # fmt: skip
        d["criteria"] = {"dnp01": ok[0], "mn9": ok[1], "m_loom": ok[2]}
        return GateResult(
            name,
            all(ok),
            float(sum(ok)),
            3.0,
            {"metric_is": "number of ablation criteria met", **d},
        )

    if name == "G6":
        with mp.get_context("spawn").Pool(workers) as pool:
            variants = pool.map(variant_worker, list(c["variants"].items()))
        n_ok = sum(v["passed"] for v in variants)
        return GateResult(name, n_ok == len(variants), float(n_ok), float(len(variants)),
                          {"metric_is": "number of variants that keep sign and monotonicity", "variants": variants})  # fmt: skip

    if name == "G7":
        s = suppression(make_runner(), c["sugar"], c["looming_levels"], c["n_rep"], c["seed_base"])
        levels = list(s["levels"])
        adj = holm([s["levels"][lv]["p"] for lv in levels])
        for lv, a in zip(levels, adj, strict=True):
            s["levels"][lv]["p_holm"] = a
        return GateResult(name, bool(min(adj) < c["alpha_level"]), float(min(adj)), c["alpha_level"],
                          {"metric_is": "smallest Holm-adjusted exact McNemar p over the looming levels", **s})  # fmt: skip
    raise ValueError(f"unknown gate {name!r}")
