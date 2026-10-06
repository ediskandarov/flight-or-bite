"""Numbers of the final report, computed from artefacts only (SPEC §10): no simulation, no API.

Everything here is listed in PREREG.md. Where PREREG.md is silent, the reading is fixed in
`READINGS` below; it was written and committed before any table or test result was looked at.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.stats import spearmanr

from flight_or_bite.policy_table.table import AXES, PolicyTable
from flight_or_bite.types import Action

ONLINE, SAMPLED = Path("reports/online/test"), Path("reports/online/test_sampled")
TABLES, CONFIRM, LATENCY = Path("reports/tables"), Path("reports/confirm"), Path("reports/latency")
JEV_MODES = ("informed", "naive", "informed_bucketed", "bucketed")
MAIN = ("connectome", "jev_informed")
BOOT, SEED = 10_000, 20260920

READINGS = [
    "RQ3, logistic-fit slices: `p_escape(looming)` at sugar = 0, bitter = 0, hunger = 0.5; "
    "`p_eat(bitter)` at sugar = 0.667 (grid node nearest 0.6), looming = 0, hunger = 0.5. Fit "
    "p = 1 / (1 + exp(−k·(x − x0))) by least squares over nodes; threshold = x0, slope = k. "
    "For the deterministic oracle the fit is degenerate: report the midpoint between nodes where the decision changes.",
    "RQ3, Jensen–Shannon divergence: base 2, between node policies (means over repetitions), "
    "unweighted mean over the 1,225 nodes of grid B.",
    "RQ4: prediction is `probabilities[ESCAPE]` for each repetition at each node (copies in bucketed modes "
    "are included: nodes differ and each has its own oracle label); outcome is “ESCAPE is optimal according to the oracle” at that node; "
    "reliability table uses 10 equal probability intervals.",
    "H6, Jev: as for connectome, Spearman ρ is computed between node difficulty d (from Jev's own policy) and median "
    "node `t_wall`, bootstrapping over nodes; per-call ρ is reported additionally and is excluded from the criterion.",
    "Speed-versus-quality figure: X-axis CI from bootstrapping decision p50 (2,000 resamples); Y-axis CI from "
    "bootstrapping `% of oracle` over episodes (seeds resampled jointly for all arbiters).",
    "Decision cost (SPEC §7): mean `t_wall` per decision and total `t_wall` per episode in the main run.",
]


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines()] if path.is_file() else []


def _json(path: Path) -> Any:
    return json.loads(path.read_text()) if path.is_file() else None


# ---------------------------------------------------------------- main metric (PREREG §2), time (§8)


def online(out: Path, deadlines: list[float]) -> dict[str, Any] | None:
    from flight_or_bite.eval.online import load_episodes, paired_only, summary_of

    if not (out / "episodes.jsonl").is_file():
        return None
    s = summary_of(out)
    by = paired_only(load_episodes(out))
    life = {n: np.array([r.lifetime for r in rs], dtype=float) for n, rs in by.items()}
    s["lifetimes"] = {n: v.tolist() for n, v in life.items()}
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, s["episodes"], size=(BOOT, s["episodes"]))
    means = {n: v[idx].mean(axis=1) for n, v in life.items()}
    for n, row in s["arbiters"].items():
        pct = (means[n] - means["random"]) / (means["oracle"] - means["random"])
        row["percent_of_oracle_ci95"] = [float(x) for x in np.percentile(pct, [2.5, 97.5])]
    keep = {(r.arbiter, r.seed) for rs in by.values() for r in rs}
    dec = pd.DataFrame([d for d in _jsonl(out / "decisions.jsonl") if (d["arbiter"], d["seed"]) in keep])
    dec = dec.drop_duplicates(["arbiter", "seed", "trial"], keep="last")  # a replayed episode is counted once
    s["retried_decisions"] = {n: int(g["retried"].gt(0).sum()) for n, g in dec.groupby("arbiter")}
    timed = dec[dec["retried"] == 0]
    s["latency"], s["deadline_share"], s["walls_ms"], s["sims_ms"] = {}, {"wall": {}, "native": {}}, {}, {}
    for n, g in timed.groupby("arbiter"):
        wall = g["t_wall_ns"].to_numpy() / 1e6
        boot = np.median(wall[rng.integers(0, len(wall), size=(2000, min(len(wall), 5000)))], axis=1)
        lat = {"n": len(wall), "p50_ms": float(np.percentile(wall, 50)), "p95_ms": float(np.percentile(wall, 95)),
               "p50_ci95": [float(x) for x in np.percentile(boot, [2.5, 97.5])], "mean_ms": float(wall.mean()),
               "per_episode_s": float(wall.sum() / 1e3 / g["seed"].nunique())}  # fmt: skip
        native = wall
        if g["t_sim_ms"].notna().all():
            sim = g["t_sim_ms"].to_numpy(dtype=float)
            lat |= {"t_sim_p50_ms": float(np.percentile(sim, 50)), "t_sim_p95_ms": float(np.percentile(sim, 95)),
                    "rtf": float(sim.sum() / wall.sum())}  # fmt: skip
            native = sim
            s["sims_ms"][n] = sim.tolist()
        s["latency"][n] = lat
        s["walls_ms"][n] = wall.tolist()
        s["deadline_share"]["wall"][n] = {str(d): float((wall <= d).mean()) for d in deadlines}
        s["deadline_share"]["native"][n] = {str(d): float((native <= d).mean()) for d in deadlines}
    return s


# ---------------------------------------------------------------- tables: RQ3, RQ4, H6 secondary (§7, §8)


def load_tables() -> dict[str, PolicyTable]:
    out = {}
    for name in ("connectome", *(f"jev_{m}" for m in JEV_MODES)):
        try:
            out[name] = PolicyTable.load(TABLES / name)
        except (FileNotFoundError, ValueError):
            pass
    return out


def oracle_probs(grid) -> np.ndarray:
    from flight_or_bite.arbiters.oracle import OracleArbiter
    from flight_or_bite.arena.env import load_env_config

    oracle = OracleArbiter(load_env_config())
    p = np.zeros((*grid.shape, 3))
    for index in grid.points():
        probs = oracle.policy(grid.observation(index))[0]
        p[index] = [probs[a] for a in (Action.EAT, Action.ESCAPE, Action.IDLE)]
    return p


def js(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    m = (p + q) / 2

    def kl(a, b):
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(a > 0, a * np.log2(a / b), 0.0).sum(axis=-1)

    return (kl(p, m) + kl(q, m)) / 2


def logistic_fit(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    if np.all((y == 0) | (y == 1)):  # a step: the fit is degenerate
        flips = np.flatnonzero(np.diff(y) != 0)
        return {"threshold": float((x[flips[0]] + x[flips[0] + 1]) / 2) if len(flips) else None, "slope": None,
                "degenerate": True}  # fmt: skip
    try:
        (x0, k), _ = curve_fit(lambda t, x0, k: 1 / (1 + np.exp(-k * (t - x0))), x, y, p0=[0.5, 5.0 * np.sign(y[-1] - y[0] or 1)],
                               bounds=([-2, -200], [3, 200]), maxfev=20000)  # fmt: skip
        return {"threshold": float(x0), "slope": float(k), "degenerate": False}
    except RuntimeError:
        return {"threshold": None, "slope": None, "degenerate": False}


def psychometrics(policies: dict[str, np.ndarray], grid) -> dict[str, Any]:
    ax = {a: np.asarray(grid.axes[a]) for a in AXES}
    at = lambda a, v: int(np.abs(ax[a] - v).argmin())  # noqa: E731
    s0, s6, b0, l0, h5 = at("sugar", 0), at("sugar", 0.6), at("bitter", 0), at("looming", 0), at("hunger", 0.5)
    out: dict[str, Any] = {"escape_vs_looming": {}, "eat_vs_bitter": {}, "x_looming": ax["looming"].tolist(),
                           "x_bitter": ax["bitter"].tolist()}  # fmt: skip
    for n, p in policies.items():  # p[..., (EAT, ESCAPE, IDLE)]
        esc, eat = p[s0, b0, :, h5, 1], p[s6, :, l0, h5, 0]
        out["escape_vs_looming"][n] = {"p": esc.tolist(), **logistic_fit(ax["looming"], esc)}
        out["eat_vs_bitter"][n] = {"p": eat.tolist(), **logistic_fit(ax["bitter"], eat)}
    names = list(policies)
    out["js_mean"] = {f"{a} vs {b}": float(js(policies[a], policies[b]).mean())
                      for i, a in enumerate(names) for b in names[i + 1 :]}  # fmt: skip
    hm = lambda p: p[:, b0, :, h5, 1].tolist()  # noqa: E731  p_escape(sugar, looming) at bitter 0, hunger 0.5
    out["heatmaps"] = {n: hm(p) for n, p in policies.items()}
    out["x_sugar"] = ax["sugar"].tolist()
    return out


def sessions_js(table: PolicyTable) -> float | None:
    df = table.rows
    if df is None or df["session"].nunique() < 2:
        return None
    cols = ["p_eat", "p_escape", "p_idle"]
    per = [g.groupby([f"i_{a}" for a in AXES])[cols].mean().to_numpy() for _, g in df.groupby("session")]
    return float(js(*(p / p.sum(axis=1, keepdims=True) for p in per[:2])).mean())


def calibration(table: PolicyTable, oracle: np.ndarray) -> dict[str, Any]:
    df = table.rows
    label = oracle[..., 1][tuple(df[f"i_{a}"].to_numpy() for a in AXES)]
    p = df["p_escape"].to_numpy() / df[["p_eat", "p_escape", "p_idle"]].sum(axis=1).to_numpy()
    bins = np.clip((p * 10).astype(int), 0, 9)
    rel = [{"bin": f"{k / 10:.1f}–{(k + 1) / 10:.1f}", "n": int((bins == k).sum()),
            "mean_p": float(p[bins == k].mean()) if (bins == k).any() else None,
            "share_optimal": float(label[bins == k].mean()) if (bins == k).any() else None} for k in range(10)]  # fmt: skip
    return {"brier": float(((p - label) ** 2).mean()), "base_rate": float(label.mean()), "n": len(p),
            "brier_of_base_rate": float(((label.mean() - label) ** 2).mean()), "reliability": rel}  # fmt: skip


def _rho_ci(d: np.ndarray, t: np.ndarray, rng: np.random.Generator) -> dict[str, Any]:
    if len(d) < 5:
        return {"n_points": len(d), "rho": None, "ci95": None}
    idx = rng.integers(0, len(d), size=(BOOT, len(d)))
    boot = np.array([spearmanr(d[i], t[i]).statistic for i in idx])
    return {"n_points": len(d), "rho": float(spearmanr(d, t).statistic),
            "ci95": [float(x) for x in np.nanpercentile(boot, [2.5, 97.5])]}  # fmt: skip


def chronometric(table: PolicyTable, column: str, *, drop_idle: bool, min_mass: float | None) -> dict[str, Any]:
    """rho(d, median latency per grid point), d = 1 - |p_escape - p_eat| (PREREG §8)."""
    df = table.rows
    df = df[~df["cache_hit"] & (df["retried"] == 0)]
    if drop_idle:
        df = df[df["action"] != Action.IDLE.value]
    keys = [f"i_{a}" for a in AXES]
    scale = 1e6 if column == "t_wall_ns" else 1.0
    med = df.groupby(keys)[column].median() / scale
    pts = pd.DataFrame({"t": med})
    # d from the node's policy; table.probs is ordered like ACTIONS
    from flight_or_bite.arbiters.base import ACTIONS

    e, x = ACTIONS.index(Action.EAT), ACTIONS.index(Action.ESCAPE)
    pts["d"] = [1 - abs(table.probs[i][x] - table.probs[i][e]) for i in pts.index]
    pts["mass"] = [table.probs[i][x] + table.probs[i][e] for i in pts.index]
    if min_mass is not None:
        pts = pts[pts["mass"] >= min_mass]
    rng = np.random.default_rng(SEED)
    out = _rho_ci(pts["d"].to_numpy(), pts["t"].to_numpy(), rng)
    out["points"] = pts[["d", "t"]].to_numpy().tolist()
    return out


def tables() -> dict[str, Any] | None:
    from flight_or_bite.arbiters.base import ACTIONS

    tabs = load_tables()
    if not tabs:
        return None
    grid = next(iter(tabs.values())).grid
    order = [ACTIONS.index(a) for a in (Action.EAT, Action.ESCAPE, Action.IDLE)]
    oracle = oracle_probs(grid)
    policies = {n: t.probs[..., order] for n, t in tabs.items()} | {"oracle": oracle}
    out: dict[str, Any] = {"available": list(tabs), "psychometrics": psychometrics(policies, grid)}
    out["sessions_js"] = {n: sessions_js(t) for n, t in tabs.items() if n.startswith("jev_")}
    out["calibration"] = {n: calibration(t, oracle) for n, t in tabs.items() if n.startswith("jev_")}
    out["rows"] = {n: {"rows": len(t.rows), "queried": int((~t.rows["cache_hit"]).sum()),
                       "retried": int((t.rows["retried"] > 0).sum()),
                       "sessions": sorted(int(x) for x in t.rows["session"].unique())} for n, t in tabs.items()}  # fmt: skip
    if "connectome" in tabs:
        out["h6_secondary_connectome"] = chronometric(tabs["connectome"], "t_sim_ms", drop_idle=True, min_mass=0.5)
    if "jev_informed" in tabs:
        jev = chronometric(tabs["jev_informed"], "t_wall_ns", drop_idle=False, min_mass=None)
        lo_hi = jev["ci95"]
        jev["equivalence_shown"] = bool(lo_hi and lo_hi[0] >= -0.1 and lo_hi[1] <= 0.1)
        df = tabs["jev_informed"].rows
        df = df[~df["cache_hit"] & (df["retried"] == 0)]
        d_of = {i: 1 - abs(policies["jev_informed"][i][1] - policies["jev_informed"][i][0]) for i in grid.points()}
        d_call = np.array([d_of[tuple(r)] for r in df[[f"i_{a}" for a in AXES]].to_numpy()])
        jev["per_call_rho"] = float(spearmanr(d_call, df["t_wall_ns"].to_numpy()).statistic)
        jev["per_call_n"] = len(df)
        out["h6_jev"] = jev
    return out


# ---------------------------------------------------------------- everything


def collect() -> dict[str, Any]:
    from flight_or_bite.timing import bench

    deadlines = bench.load_cfg()["deadlines_ms"]
    gates = {p.stem: json.loads(p.read_text()) for p in sorted(Path("reports/gates").glob("G*.json"))}
    return {
        "main": online(ONLINE, deadlines), "sampled": online(SAMPLED, deadlines),
        "confirm": _json(CONFIRM / "confirm.json"), "h5": _json(CONFIRM / "h5.json"),
        "tables": tables(), "latency": bench.summary(LATENCY) if LATENCY.is_dir() else None,
        "gates": gates, "deadlines": deadlines, "ledger": _json(Path("runs/jev_ledger.json")),
        "test_access": (Path("runs/test_access.log").read_text().splitlines()
                        if Path("runs/test_access.log").is_file() else []),
        "readings": READINGS,
    }  # fmt: skip
