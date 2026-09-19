"""`fob perf`: benchmark every LIF backend candidate and write reports/perf.md (SPEC §11, M1)."""

from __future__ import annotations

import gc
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from flight_or_bite import sysinfo
from flight_or_bite.lif.backend import Stimulus
from flight_or_bite.lif.backends import BACKEND_NAMES, make_backend
from flight_or_bite.lif.circuits import load_circuits, resolve
from flight_or_bite.lif.data import load_manifest
from flight_or_bite.lif.graph import load_connectome
from flight_or_bite.lif.params import load_params
from flight_or_bite.lif.perf import BackendPerf, bench_backend, spike_pairs, throttle_check
from flight_or_bite.runlog import start_run, write_json

BENCH_RATE_HZ = 150.0  # the authors' default `r_poi`, so numbers are comparable with their example
SEED_BASE = 3_000_000
GRID_SIMS = {"connectome (225 points x 20)": 4_500, "shuffled (2 slices)": 2_000}


def _verify(name: str, backend, reference, stimulus, t_ms: float, dt_ms: float) -> dict[str, Any]:
    """Spike-for-spike comparison of `backend` with `reference` on identical input."""
    from flight_or_bite.lif.event_backend import replay_schedule

    same, total = 0, 0
    for seed in (SEED_BASE + 900, SEED_BASE + 901):
        ref = reference.run_trial(stimulus, t_ms, seed=seed)
        kicks = replay_schedule(ref.spike_i, ref.spike_t_ms, stimulus.neurons, dt_ms)
        got = backend.run_trial(stimulus, t_ms, seed=seed, kicks=kicks)
        a, b = spike_pairs(ref, dt_ms), spike_pairs(got, dt_ms)
        same += len(a & b)
        total += len(a | b)
    return {"backend": name, "reference": reference.name, "identical": same, "union": total}


def run_perf(
    console: Console,
    backends: list[str] | None,
    version: int | None,
    n_full: int,
    n_stop: int,
    out: Path,
) -> None:
    params = load_params()
    encoding = yaml.safe_load(Path("configs/encoding.yaml").read_text())
    version = version or params.connectome_version
    names = backends or list(BACKEND_NAMES)
    t_ms = float(encoding["t_sim_ms"])
    run_dir = start_run(
        "perf",
        {"lif": params.model_dump(), "version": version, "backends": names, "t_ms": t_ms,
         "rate_hz": BENCH_RATE_HZ, "n_full": n_full, "n_stop": n_stop},
        seeds={"seed_base": SEED_BASE},
    )  # fmt: skip

    throttle = throttle_check()
    console.print(f"throttle check: {throttle}")
    t0 = time.perf_counter()
    connectome = load_connectome(load_manifest(Path("configs/data.yaml")), version, Path("data"))
    t_graph_s = time.perf_counter() - t0
    circuits = load_circuits()
    stimulus = Stimulus.uniform(resolve(connectome, circuits["sugar_grn_right"]), BENCH_RATE_HZ)
    mn9 = int(resolve(connectome, circuits["mn9"])[0])

    perfs: list[BackendPerf] = []
    failures: dict[str, str] = {}
    checks: list[dict[str, Any]] = []
    reference = None
    for name in sorted(names, key=lambda n: n != "brian2"):  # reference first
        console.print(f"benchmarking {name} ...")
        try:
            backend = make_backend(name, connectome, params)
            perf, _ = bench_backend(
                backend, stimulus, mn9, t_ms=t_ms, n_full=n_full, n_stop=n_stop, seed_base=SEED_BASE
            )
        except Exception as e:  # a candidate that cannot run is a finding, not a crash
            failures[name] = f"{type(e).__name__}: {e}"
            console.print(f"[red]{name} failed: {failures[name]}[/]")
            continue
        perf.backend = name  # the factory name is the key used throughout the report
        perfs.append(perf)
        console.print(f"  wall p50 {perf.full_wall_s_p50:.3f}s  RTF {perf.rtf_p50:.2f}")
        if name == "brian2":
            reference = backend
            continue
        if reference is not None:
            checks.append(_verify(name, backend, reference, stimulus, t_ms, params.dt_ms))
        del backend
        gc.collect()

    payload = {
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": sysinfo.collect().as_dict(),
        "throttle": throttle,
        "connectome": {"version": version, "neurons": connectome.n_neurons,
                       "edges": connectome.n_edges, "t_graph_load_s": t_graph_s},
        "protocol": {"t_ms": t_ms, "rate_hz": BENCH_RATE_HZ, "n_stimulated": len(stimulus.neurons),
                     "n_full": n_full, "n_stop": n_stop, "stop_rule": "first MN9 spike"},
        "backends": [p.as_dict() for p in perfs],
        "failures": failures,
        "verification": checks,
        "run_dir": str(run_dir),
    }  # fmt: skip
    write_json(run_dir / "perf.json", payload)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(payload))
    console.print(f"[green]wrote {out}[/] (raw numbers: {run_dir / 'perf.json'})")


def _hours(sims: int, wall_s: float, workers: int = 1) -> str:
    h = sims * wall_s / 3600 / workers
    return f"{h * 60:.0f} min" if h < 1 else f"{h:.1f} h"


def render(d: dict[str, Any]) -> str:
    host, thr, con, pro = d["host"], d["throttle"], d["connectome"], d["protocol"]
    workers = host.get("performance_cores") or 1
    lines = [
        "# LIF backend benchmark",
        "",
        f"Generated {d['generated']} by `fob perf`; raw numbers in `{d['run_dir']}/perf.json`.",
        "",
        "## Conditions",
        "",
        f"- Host: {host['chip']}, {host['performance_cores']}P + {host['efficiency_cores']}E cores, "
        f"{host['memory_gb']} GB, {host['os_version']}, Python {host['python']}.",
        f"- Power: {thr['power']}.",
        f"- Timer throttling self-check: `sleep(10 ms)` overshoots by a median of "
        f"{thr['sleep_10ms_overshoot_ms_median']} ms (max {thr['sleep_10ms_overshoot_ms_max']} ms)"
        f" -> **{'THROTTLED process' if thr['timer_throttled'] else 'not throttled'}**.",
        f"- Connectome v{con['version']}: {con['neurons']:,} neurons, {con['edges']:,} edges; "
        f"parquet -> CSR in {con['t_graph_load_s']:.2f} s.",
        f"- Protocol (SPEC §6.2): one process, graph in memory, {pro['n_stimulated']} sugar GRNs at "
        f"{pro['rate_hz']:.0f} Hz, window {pro['t_ms']:.0f} ms, dt 0.1 ms. `t_wall` covers input "
        f"generation, state reset and simulation. {pro['n_full']} full trials and {pro['n_stop']} "
        f"early-stop trials ({pro['stop_rule']}) per backend, after one warm-up trial.",
        "",
    ]
    if thr["timer_throttled"]:
        lines += [
            "> **These numbers come from a throttled process** (launched by the coding agent). They",
            "> are valid for ranking the backends, not as the project's `t_wall` figures. Decision",
            "> D5: re-run `uv run fob perf` from your own terminal, on AC power, under `caffeinate -i`.",
            "",
        ]
    lines += [
        "## Results",
        "",
        "| Backend | t_load, s | First trial, s | Full trial wall p50, s | max, s | **RTF p50** | "
        "Spikes / trial | MN9, Hz | Early stop: fired | t_sim p50, ms | wall p50, s |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for p in d["backends"]:
        lines.append(
            f"| `{p['backend']}` | {p['t_load_s']:.2f} | {p['first_trial_wall_s']:.2f} | "
            f"{p['full_wall_s_p50']:.3f} | {p['full_wall_s_max']:.3f} | **{p['rtf_p50']:.2f}** | "
            f"{p['spikes_per_trial']:,.0f} | {p['mn9_rate_hz']:.1f} | {p['stop_fraction']:.0%} | "
            f"{p['stop_t_sim_ms_p50']:.1f} | {p['stop_wall_s_p50']:.3f} |"
        )
    for name, why in d["failures"].items():
        lines.append(f"| `{name}` | failed: {why} | | | | | | | | | |")
    lines += [
        "",
        "RTF = simulated time / wall time; above 1 is faster than real time. *First trial* includes",
        "one-off costs (code generation, cache warm-up) and is excluded from the other columns.",
        "",
        "## Verification against the Brian2 reference",
        "",
        "Input spikes recorded in a Brian2 trial are replayed into the candidate; all spikes of the",
        "whole network are then compared as (neuron, time step) pairs over two trials.",
        "",
        "| Backend | Identical pairs | Union | Verdict |",
        "|---|---|---|---|",
    ]
    for c in d["verification"]:
        verdict = "**bit-identical**" if c["identical"] == c["union"] else "differs"
        lines.append(f"| `{c['backend']}` | {c['identical']:,} | {c['union']:,} | {verdict} |")
    if not d["verification"]:
        lines.append("| — | not run (needs `brian2` plus one candidate) | | |")

    lines += ["", "## Cost of the default grid (SPEC §4.5)", ""]
    lines += [
        f"| Backend | {' | '.join(GRID_SIMS)} | both, 1 process | both, {workers} workers |",
        f"|---|{'---|' * (len(GRID_SIMS) + 2)}",
    ]
    for p in d["backends"]:
        w = p["full_wall_s_p50"]
        cells = " | ".join(_hours(n, w) for n in GRID_SIMS.values())
        total = sum(GRID_SIMS.values())
        lines.append(
            f"| `{p['backend']}` | {cells} | {_hours(total, w)} | {_hours(total, w, workers)} |"
        )
    lines += [
        "",
        "Extrapolated from the sugar-only trial above, without early stopping. Trials that also",
        "drive the looming channel will activate more of the network and cost more; that is unknown",
        "until the LPLC2 / LC4 sets exist (M3). The multi-worker column assumes linear scaling.",
        "",
    ]
    lines += _recommendation(d, workers)
    return "\n".join(lines)


# (sugar, bitter, looming, hunger) points, connectome N_rep, Jev N_rep. Jev has 3 state modes (D7).
GRID_OPTIONS = {
    "A. SPEC default": ((5, 3, 5, 3), 20, 20),
    "B. finer stimulus axes": ((7, 5, 7, 5), 20, 10),
    "C. fine": ((9, 5, 9, 5), 30, 10),
}
JEV_SECONDS_PER_CALL = 0.4  # p50 measured at M0 through OpenRouter (docs/jev_api_notes.md §11)
JEV_MODES = 3


def _recommendation(d: dict[str, Any], workers: int) -> list[str]:
    verified = {c["backend"] for c in d["verification"] if c["identical"] == c["union"]}
    eligible = [
        p for p in d["backends"] if p["backend"] in verified or p["backend"].startswith("brian2")
    ]
    if not eligible:
        return ["## Recommendation", "", "No backend could be benchmarked; see failures above.", ""]
    best = max(eligible, key=lambda p: p["rtf_p50"])
    ref = next((p for p in d["backends"] if p["backend"].startswith("brian2")), None)
    lines = ["## Recommendation", ""]
    speedup = f", {best['rtf_p50'] / ref['rtf_p50']:.1f}x the Brian2 reference" if ref else ""
    lines += [
        f"**Backend: `{best['backend']}`** — RTF {best['rtf_p50']:.2f}{speedup}, and "
        + (
            "bit-identical to Brian2 on replayed input."
            if best["backend"] in verified
            else "it is the reference itself."
        ),
        "Brian2 stays in the test suite as the reference. Only backends that passed verification",
        "are eligible; a faster but unverified backend is never recommended.",
        "",
        "### Grid size — proposal for the human (SPEC §4.5)",
        "",
        f"Connectome cost uses `{best['backend']}` at {best['full_wall_s_p50']:.3f} s per trial "
        f"on {workers} workers; Jev cost assumes {JEV_SECONDS_PER_CALL} s per sequential call and "
        f"{JEV_MODES} state modes.",
        "",
        "| Option | Grid (sugar x bitter x looming x hunger) | Points | Connectome sims | "
        "Connectome time | Jev calls | Jev time |",
        "|---|---|---|---|---|---|---|",
    ]
    for label, (shape, n_con, n_jev) in GRID_OPTIONS.items():
        points = shape[0] * shape[1] * shape[2] * shape[3]
        sims, calls = points * n_con, points * JEV_MODES * n_jev
        lines.append(
            f"| {label} | {' x '.join(map(str, shape))} | {points:,} | {sims:,} (N_rep {n_con}) | "
            f"{_hours(sims, best['full_wall_s_p50'], workers)} | {calls:,} (N_rep {n_jev}) | "
            f"{_hours(calls, JEV_SECONDS_PER_CALL)} |"
        )
    lines += [
        "",
        "The connectome is no longer the bottleneck: Jev's sequential latency is. Suggested: **B**,",
        "to be confirmed after M3, when the cost of trials with the looming channel is known. Finer",
        "stimulus axes matter most for RQ3 (psychometric thresholds and slopes) and for the",
        "interpolation error checked by the live episodes (SPEC §7).",
        "",
    ]
    return lines
