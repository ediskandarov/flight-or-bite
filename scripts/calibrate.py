"""Channel calibration (decision D25). Protocol: configs/calibration.yaml. Connectome v783,
event backend, full 500 ms trials decoded afterwards. Writes runs/<ts>_calibration/calibration.json."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from flight_or_bite.lif.backend import Stimulus
from flight_or_bite.lif.backends import make_backend
from flight_or_bite.lif.circuits import load_circuits, resolve
from flight_or_bite.lif.data import load_manifest
from flight_or_bite.lif.decoder import decode, spikes_needed
from flight_or_bite.lif.graph import load_connectome
from flight_or_bite.lif.params import load_params
from flight_or_bite.runlog import start_run, write_json
from flight_or_bite.types import Action

cal = yaml.safe_load(Path("configs/calibration.yaml").read_text())
T_MS = float(yaml.safe_load(Path("configs/encoding.yaml").read_text())["t_sim_ms"])
params = load_params()
con = load_connectome(
    load_manifest(Path("configs/data.yaml")), params.connectome_version, Path("data")
)
circuits = load_circuits()
sugar_n = resolve(con, circuits["sugar_grn_right"])
loom_n = np.concatenate([resolve(con, circuits["lplc2"]), resolve(con, circuits["lc4"])])
mn9, dnp01 = int(resolve(con, circuits["mn9"])[0]), resolve(con, circuits["dnp01"])
backend = make_backend("event", con, params)
run_dir = start_run("calibration", {"protocol": cal, "lif": params.model_dump(), "t_sim_ms": T_MS,
                                    "n_sugar_grn": len(sugar_n), "n_looming": len(loom_n)})  # fmt: skip
W = float(cal["eat_window_ms"])

# ---- 1. MN9 saturation -> theta_eat ---------------------------------------------------------
sat = []
for drive in cal["saturation"]["drives_hz"]:
    rates = [backend.run_trial(Stimulus.uniform(sugar_n, drive), T_MS, seed=s).rate_hz(mn9)
             for s in range(cal["saturation"]["n_trials"])]  # fmt: skip
    sat.append(
        {"drive_hz": drive, "mn9_rate_hz_mean": float(np.mean(rates)), "sd": float(np.std(rates))}
    )
    print("saturation", sat[-1], flush=True)
saturation_hz = max(r["mn9_rate_hz_mean"] for r in sat)
theta = cal["theta_fraction"] * saturation_hz
print(
    f"saturation {saturation_hz:.2f} Hz -> theta_eat {theta:.2f} Hz = {spikes_needed(theta, W)} spikes in {W:.0f} ms",
    flush=True,
)


def p_response(neurons, drive_hz: float, want: Action, seeds) -> tuple[float, list]:
    rows = []
    for s in seeds:
        r = backend.run_trial(Stimulus.uniform(neurons, drive_hz), T_MS, seed=s)
        rows.append(decode(r, mn9, dnp01, theta_eat_hz=theta, eat_window_ms=W, t_sim_ms=T_MS))
    return float(np.mean([d.action is want for d in rows])), rows


def bisect(channel: str, neurons, want: Action) -> dict:
    b = cal["bisection"]
    lo, hi = b["bracket_hz"][channel]
    seeds = range(b["n_trials"])
    p_lo, _ = p_response(neurons, b["stimulus"] * lo, want, seeds)
    p_hi, _ = p_response(neurons, b["stimulus"] * hi, want, seeds)
    steps = [{"r_max": lo, "p": p_lo}, {"r_max": hi, "p": p_hi}]
    if not (p_lo < b["target_p"] < p_hi):
        return {"ok": False, "steps": steps}
    for _ in range(b["max_steps"]):
        mid = 0.5 * (lo + hi)
        p, _ = p_response(neurons, b["stimulus"] * mid, want, seeds)
        steps.append({"r_max": mid, "p": p})
        print(f"  {want.value}: R_max {mid:.3f} Hz -> p {p:.2f}", flush=True)
        if p < b["target_p"]:
            lo = mid
        else:
            hi = mid  # p >= target: the smallest R_max reaching the target
        if hi - lo < b["tolerance_hz"]:
            break
    return {"ok": True, "r_max_hz": hi, "bracket": [lo, hi], "steps": steps}


sugar_fit = bisect("sugar", sugar_n, Action.EAT)
loom_fit = bisect("looming", loom_n, Action.ESCAPE)

# ---- 3. verification curves on fresh dev seeds -------------------------------------------
v = cal["verification"]
levels = np.round(np.linspace(0, 1, v["levels"]), 2)
seeds = range(500, 500 + v["n_trials"])
curves = {}
for name, neurons, fit, want in (
    ("sugar", sugar_n, sugar_fit, Action.EAT),
    ("looming", loom_n, loom_fit, Action.ESCAPE),
):
    if not fit["ok"]:
        continue
    rows = []
    for level in levels:
        p, decoded = p_response(neurons, float(level) * fit["r_max_hz"], want, seeds)
        t = [d.t_sim_ms for d in decoded if d.action is want]
        other = {a.value: float(np.mean([d.action is a for d in decoded])) for a in Action}
        rows.append({"level": float(level), "drive_hz": float(level * fit["r_max_hz"]), "p_response": p,
                     "t_sim_ms_p50": float(np.median(t)) if t else None,
                     "t_sim_ms_range": [float(min(t)), float(max(t))] if t else None, "actions": other})  # fmt: skip
        print(name, rows[-1]["level"], rows[-1]["p_response"], rows[-1]["t_sim_ms_p50"], flush=True)
    curves[name] = rows

write_json(run_dir / "calibration.json", {
    "saturation_sweep": sat, "mn9_saturation_hz": saturation_hz, "theta_eat_hz": theta,
    "eat_window_ms": W, "spikes_needed": spikes_needed(theta, W), "sugar": sugar_fit, "looming": loom_fit,
    "verification": curves, "run_dir": str(run_dir),
})  # fmt: skip
print("DONE", run_dir, flush=True)
