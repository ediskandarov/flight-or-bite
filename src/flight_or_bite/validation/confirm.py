"""Confirmatory analyses H1-H4, H6 and the planned robustness analysis (PREREG §3, §4, §8).

Protocol: configs/confirm.yaml (hashed in PREREG.md). Run only after the preregistration is frozen.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy.stats import binomtest, wilcoxon

from flight_or_bite.eval.stats import holm, mcnemar_exact
from flight_or_bite.lif.trial import Trial
from flight_or_bite.types import Action, Observation
from flight_or_bite.validation.gates_m3 import EAT_WINDOW_S, make_runner


def load_cfg() -> dict[str, Any]:
    cfg = yaml.safe_load(Path("configs/confirm.yaml").read_text())
    if os.environ.get("FOB_CONFIRM_SMOKE") == "1":  # crash test: tiny, on unrelated seeds
        cfg["n_pairs"] = 4
        cfg["seed_base"] += 50_000_000
        cfg["H2"]["permutations"] = 200
        cfg["H5"] |= {"jev_reps": 2, "connectome_trials": 2, "bootstrap": 200}
    return cfg


def seeds(cfg: dict, hypothesis: int, level_index: int, offset: int = 0) -> list[int]:
    base = cfg["seed_base"] + offset + 1000 * hypothesis + 100 * level_index
    return [base + r for r in range(cfg["n_pairs"])]


def arm(runner, cfg, hypothesis: int, *, sugar: float, hunger: float = 0.0, ablated=None,
        eat_spikes: int | None = None, offset: int = 0) -> dict[str, list[Trial]]:  # fmt: skip
    theta = None if eat_spikes is None else (eat_spikes - 0.5) / EAT_WINDOW_S
    return {
        str(lv): [runner.run(Observation(sugar, 0.0, lv, hunger), s, ablated=ablated, theta_eat_hz=theta)
                  for s in seeds(cfg, hypothesis, li, offset)]
        for li, lv in enumerate(cfg["looming_levels"])
    }  # fmt: skip


def spiked(trials: list[Trial]) -> list[bool]:
    return [t.dnp01_spiked for t in trials]


def escaped(trials: list[Trial]) -> list[bool]:
    return [t.decoded.action is Action.ESCAPE for t in trials]


def with_holm(per_level: dict[str, dict], alpha: float) -> dict[str, Any]:
    levels = list(per_level)
    for lv, p in zip(levels, holm([per_level[lv]["p"] for lv in levels]), strict=True):
        per_level[lv]["p_holm"] = p
    best = min(levels, key=lambda lv: per_level[lv]["p_holm"])
    return {"levels": per_level, "min_p_holm": per_level[best]["p_holm"], "best_level": best, "alpha": alpha}


def mcnemar_hypothesis(control, condition, outcome, alpha) -> dict[str, Any]:
    out = with_holm({lv: mcnemar_exact(outcome(control[lv]), outcome(condition[lv])) for lv in control}, alpha)
    direction = all(x["b"] > x["c"] for x in out["levels"].values() if x["b"] + x["c"] > 0)
    out["confirmed"] = bool(out["min_p_holm"] < alpha and direction)
    out["b_gt_c_wherever_discordant"] = direction
    return out


def h1(runner, cfg) -> tuple[dict, dict, dict]:
    control, cond = arm(runner, cfg, 1, sugar=0.0), arm(runner, cfg, 1, sugar=cfg["sugar"])
    return mcnemar_hypothesis(control, cond, spiked, cfg["alpha_level"]), control, cond


def h6(control, cond, cfg) -> dict[str, Any]:
    per = {}
    for lv in control:
        pairs = [(c.decoded.t_escape_ms, x.decoded.t_escape_ms) for c, x in zip(control[lv], cond[lv], strict=True)
                 if c.dnp01_spiked and x.dnp01_spiked]  # fmt: skip
        diff = np.array([x - c for c, x in pairs])
        ok = len(pairs) >= cfg["H6"]["min_pairs"] and np.any(diff != 0)
        p = float(wilcoxon(diff, zero_method="wilcox", alternative="two-sided").pvalue) if ok else 1.0
        per[lv] = {"n_pairs": len(pairs), "p": p, "median_diff_ms": float(np.median(diff)) if len(pairs) else None,
                   "median_control_ms": float(np.median([c for c, _ in pairs])) if pairs else None,
                   "median_condition_ms": float(np.median([x for _, x in pairs])) if pairs else None}  # fmt: skip
    out = with_holm(per, cfg["alpha_level"])
    best = out["levels"][out["best_level"]]
    out["confirmed"] = bool(out["min_p_holm"] < cfg["alpha_level"] and (best["median_diff_ms"] or 0) > 0)
    return out


def h2(runner, cfg) -> dict[str, Any]:
    c = cfg["H2"]
    arms = {d: arm(runner, cfg, 2, sugar=d) for d in c["doses"]}
    rng = np.random.default_rng(c["permutation_seed"])
    ranks = np.arange(len(c["doses"]), dtype=float)
    per = {}
    for lv in arms[c["doses"][0]]:
        y = np.array([spiked(arms[d][lv]) for d in c["doses"]], dtype=float).T  # [seed, dose]
        t_obs = float((y * ranks).sum())
        count, done = 0, 0
        while done < c["permutations"]:  # permute the dose labels within every seed
            n = min(10_000, c["permutations"] - done)
            order = np.argsort(rng.random((n, *y.shape)), axis=2)
            t = (np.take_along_axis(np.broadcast_to(y, (n, *y.shape)), order, axis=2) * ranks).sum(axis=(1, 2))
            count += int((t <= t_obs + 1e-9).sum())
            done += n
        per[lv] = {"p": (count + 1) / (c["permutations"] + 1), "statistic": t_obs,
                   "spiked_by_dose": {str(d): int(y[:, k].sum()) for k, d in enumerate(c["doses"])}, "n": len(y)}  # fmt: skip
    out = with_holm(per, cfg["alpha_level"])
    out["confirmed"] = bool(out["min_p_holm"] < cfg["alpha_level"])
    return out


def h3(runner, cfg) -> dict[str, Any]:
    gone = runner.named[cfg["H3"]["ablate"]]
    cells = {k: arm(runner, cfg, 3, sugar=s, ablated=a) for k, (s, a) in
             {"c": (0.0, None), "x": (cfg["sugar"], None), "ca": (0.0, gone), "xa": (cfg["sugar"], gone)}.items()}  # fmt: skip
    rng = np.random.default_rng(20260920)
    per, pooled = {}, []
    for lv in cells["c"]:
        v = {k: np.array(spiked(cells[k][lv]), dtype=int) for k in cells}
        intact, ablated = v["c"] - v["x"], v["ca"] - v["xa"]
        d = intact - ablated
        pos, neg = int((d > 0).sum()), int((d < 0).sum())
        per[lv] = {"p": float(binomtest(pos, pos + neg, 0.5).pvalue) if pos + neg else 1.0, "d_positive": pos,
                   "d_negative": neg, "sum_d": int(d.sum()), "effect_intact": int(intact.sum()),
                   "effect_ablated": int(ablated.sum())}  # fmt: skip
        pooled.append(np.stack([intact, ablated], axis=1))
    out = with_holm(per, cfg["alpha_level"])
    best = out["levels"][out["best_level"]]
    out["confirmed"] = bool(out["min_p_holm"] < cfg["alpha_level"] and best["sum_d"] > 0)
    both = np.concatenate(pooled)
    idx = rng.integers(0, len(both), size=(10_000, len(both)))
    num, den = both[idx, 1].sum(axis=1), both[idx, 0].sum(axis=1)
    ratio = num[den > 0] / den[den > 0]
    out["retained_fraction"] = float(both[:, 1].sum() / both[:, 0].sum()) if both[:, 0].sum() else None
    out["retained_ci95"] = [float(x) for x in np.percentile(ratio, [2.5, 97.5])] if len(ratio) else None
    return out


def h4(runner, cfg) -> dict[str, Any]:
    lo, hi = cfg["H4"]["hunger"]
    control, cond = (arm(runner, cfg, 4, sugar=cfg["sugar"], hunger=h) for h in (lo, hi))
    out = mcnemar_hypothesis(control, cond, escaped, cfg["alpha_level"])
    out["additional_outcome_dnp01_spiked"] = mcnemar_hypothesis(control, cond, spiked, cfg["alpha_level"])
    return out


def robustness_worker(item: tuple[int, dict]) -> dict[str, Any]:
    number, spec = item
    cfg = load_cfg()
    runner = make_runner(**{k: v for k, v in spec.items() if k not in ("name", "hunger", "outcome", "eat_spikes")})
    kw = {"hunger": spec.get("hunger", 0.0), "eat_spikes": spec.get("eat_spikes"), "offset": 10_000 * number}
    control, cond = arm(runner, cfg, 1, sugar=0.0, **kw), arm(runner, cfg, 1, sugar=cfg["sugar"], **kw)
    outcome = escaped if spec.get("outcome") == "escape" else spiked
    res = mcnemar_hypothesis(control, cond, outcome, cfg["alpha_level"])
    return {"variant": number, "name": spec["name"], "outcome": spec.get("outcome", "dnp01_spiked"), **res}


def run_all(workers: int = 5, log=print) -> dict[str, Any]:
    cfg = load_cfg()
    runner = make_runner()
    out: dict[str, Any] = {"n_pairs": cfg["n_pairs"], "looming_levels": cfg["looming_levels"]}
    out["H1"], control, cond = h1(runner, cfg)
    log(f"H1 {out['H1']['confirmed']} {out['H1']['min_p_holm']:.3g}")
    out["H6"] = h6(control, cond, cfg)
    log(f"H6 {out['H6']['confirmed']} {out['H6']['min_p_holm']:.3g}")
    for name, fn in (("H2", h2), ("H3", h3), ("H4", h4)):
        out[name] = fn(runner, cfg)
        log(f"{name} {out[name]['confirmed']} {out[name]['min_p_holm']:.3g}")
    with mp.get_context("spawn").Pool(workers) as pool:
        out["robustness"] = pool.map(robustness_worker, list(cfg["robustness"].items()))
    return out
