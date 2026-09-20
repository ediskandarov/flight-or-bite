"""H5 (PREREG §5): shift of the escape curve by sugar - Jev (main mode) vs oracle vs connectome.

Protocol: configs/confirm.yaml, block H5 (hashed in PREREG.md). Jev answers are appended to
`reports/confirm/h5_jev.jsonl` as they arrive, so a stopped run (PREREG §2b) resumes where it was.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from flight_or_bite.types import Action, Observation
from flight_or_bite.validation.confirm import load_cfg


def points(c: dict) -> list[tuple[int, float, float]]:
    """(point_index, sugar, looming); point_index = sugar_index * n_looming + looming_index."""
    loom = [round(x, 10) for x in np.linspace(0.0, 1.0, c["looming_levels"])]
    return [(si * len(loom) + li, s, lv) for si, s in enumerate(c["sugar"]) for li, lv in enumerate(loom)]


def delta(p: np.ndarray, n_looming: int) -> np.ndarray:
    """p[..., point] -> mean over looming levels of p_escape(sugar 0.6) - p_escape(sugar 0)."""
    return (p[..., n_looming:] - p[..., :n_looming]).mean(axis=-1)


def boot_delta(samples: np.ndarray, n_looming: int, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    """samples[point, repeat]; repeats are resampled independently within every point."""
    n_pts, n_rep = samples.shape
    idx = rng.integers(0, n_rep, size=(n_boot, n_pts, n_rep))
    return delta(np.take_along_axis(np.broadcast_to(samples, (n_boot, n_pts, n_rep)), idx, axis=2).mean(axis=2),
                 n_looming)  # fmt: skip


def jev_samples(c: dict, path: Path, mock: bool, log) -> tuple[np.ndarray, list[str], int]:
    from flight_or_bite.arbiters.jev_arbiter import JevArbiter, load_prompt
    from flight_or_bite.arbiters.jev_client import JevClient, MockJevClient

    rows = [json.loads(x) for x in path.read_text().splitlines()] if path.is_file() else []
    have = {k: sum(1 for r in rows if r["point"] == k) for k, _, _ in points(c)}
    if any(n < c["jev_reps"] for n in have.values()):
        path.parent.mkdir(parents=True, exist_ok=True)
        with MockJevClient() if mock else JevClient() as client, path.open("a") as f:
            arbiter = JevArbiter(client, load_prompt(c["jev_mode"]), retries=5)
            for k, sugar, lv in points(c):
                for rep in range(have[k], c["jev_reps"]):
                    probs, meta = arbiter.policy(Observation(sugar, c["bitter"], lv, c["hunger"]))
                    row = {"point": k, "sugar": sugar, "looming": lv, "rep": rep, "p_escape": probs[Action.ESCAPE],
                           "choice": meta["native_action"].value, "retried": meta["retried"],
                           "model_version": meta["model_version"]}  # fmt: skip
                    f.write(json.dumps(row) + "\n")
                    f.flush()
                    rows.append(row)
                log(f"H5 jev: point {k + 1}/{len(have)}")
    by = {k: [r["p_escape"] for r in rows if r["point"] == k][: c["jev_reps"]] for k in have}
    return (np.array([by[k] for k in sorted(by)]), sorted({r["model_version"] for r in rows}),
            sum(r["retried"] for r in rows))  # fmt: skip


def run_h5(mock: bool = False, out_dir: Path = Path("reports/confirm"), log=print) -> dict[str, Any]:
    from flight_or_bite.arbiters.oracle import OracleArbiter
    from flight_or_bite.arena.env import load_env_config
    from flight_or_bite.validation.gates_m3 import make_runner

    cfg = load_cfg()
    c, n_lv = cfg["H5"], cfg["H5"]["looming_levels"]
    rng = np.random.default_rng(c["bootstrap_seed"])
    pts = points(c)

    jev, models, retried = jev_samples(c, out_dir / "h5_jev.jsonl", mock, log)

    oracle = OracleArbiter(load_env_config())
    orc = np.array([oracle.policy(Observation(s, c["bitter"], lv, c["hunger"]))[0][Action.ESCAPE] for _, s, lv in pts])

    runner = make_runner()
    base = cfg["seed_base"] + 1000 * c["hypothesis"]
    con = np.array([[runner.run(Observation(s, c["bitter"], lv, c["hunger"]), base + 100 * k + t).decoded.action
                     is Action.ESCAPE for t in range(c["connectome_trials"])] for k, s, lv in pts], dtype=float)  # fmt: skip
    log("H5 connectome: done")

    d_orc = float(delta(orc, n_lv))
    out: dict[str, Any] = {"looming": [lv for _, _, lv in pts[:n_lv]], "sugar": c["sugar"], "delta_oracle": d_orc,
                           "jev_mode": c["jev_mode"], "jev_models": models, "jev_retried_calls": retried}  # fmt: skip
    for name, samples in (("jev", jev), ("connectome", con)):
        boot = boot_delta(samples, n_lv, c["bootstrap"], rng)
        out[f"delta_{name}"] = float(delta(samples.mean(axis=1), n_lv))
        out[f"delta_{name}_ci95"] = [float(x) for x in np.percentile(boot, [2.5, 97.5])]
        out[f"delta_{name}_minus_oracle"] = out[f"delta_{name}"] - d_orc
        out[f"delta_{name}_minus_oracle_ci95"] = [float(x) for x in np.percentile(boot - d_orc, [2.5, 97.5])]
        out[f"p_escape_{name}"] = {str(s): samples.mean(axis=1)[i * n_lv : (i + 1) * n_lv].tolist()
                                   for i, s in enumerate(c["sugar"])}  # fmt: skip
    out["p_escape_oracle"] = {str(s): orc[i * n_lv : (i + 1) * n_lv].tolist() for i, s in enumerate(c["sugar"])}
    lo, hi = out["delta_jev_ci95"]
    out["confirmed"] = bool(lo > 0 or hi < 0)  # PREREG §5: delta_Jev != 0; the sign is reported, not tested
    return out
