"""Gate orchestration for the CLI: build backends, run, write reports/gates/<gate>.json."""

from __future__ import annotations

import gc
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from flight_or_bite.lif.backends import make_backend
from flight_or_bite.lif.circuits import load_circuits, resolve
from flight_or_bite.lif.data import load_manifest
from flight_or_bite.lif.graph import load_connectome
from flight_or_bite.lif.params import load_params
from flight_or_bite.runlog import start_run, write_json
from flight_or_bite.validation.gates import GateResult, g1_sugar_to_mn9


def run_g1(
    console: Console,
    backends: list[str],
    versions: list[int] | None,
    *,
    gates_dir: Path = Path("reports/gates"),
) -> bool:
    params = load_params()
    encoding = yaml.safe_load(Path("configs/encoding.yaml").read_text())
    cfg = yaml.safe_load(Path("configs/gates.yaml").read_text())["G1"]
    manifest = load_manifest(Path("configs/data.yaml"))
    circuits = load_circuits()
    versions = versions or sorted({params.connectome_version, 630})
    run_dir = start_run(
        "gate-G1",
        {"lif": params.model_dump(), "encoding": encoding, "G1": cfg, "backends": backends,
         "versions": versions},
        seeds={"seed_base": cfg["seed_base"]},
    )  # fmt: skip

    runs: dict[str, GateResult] = {}
    for version in versions:
        connectome = load_connectome(manifest, version, Path("data"))
        sugar = resolve(connectome, circuits["sugar_grn_right"])
        mn9 = int(resolve(connectome, circuits["mn9"])[0])
        for name in backends:
            console.print(f"G1: backend {name}, connectome v{version}, {len(sugar)} sugar GRNs ...")
            backend = make_backend(name, connectome, params)
            runs[f"{name}/v{version}"] = g1_sugar_to_mn9(
                backend, sugar, mn9,
                r_max_hz=encoding["r_max_hz"], t_sim_ms=encoding["t_sim_ms"],
                levels=cfg["levels"], n_rep=cfg["n_rep"], seed_base=cfg["seed_base"],
                threshold=cfg["threshold"],
            )  # fmt: skip
            del backend
            gc.collect()

    table = Table(title="G1: sugar -> MN9 (Spearman rho over all trials)")
    for col in ("run", "rho", "rho of means", "MN9 Hz at sugar 0 / 0.5 / 1", "passed"):
        table.add_column(col)
    for key, r in runs.items():
        m = r.details["mn9_rate_hz_mean"]
        table.add_row(
            key, f"{r.metric:.3f}", f"{r.details['rho_over_level_means']:.3f}",
            f"{m[0]:.1f} / {m[len(m) // 2]:.1f} / {m[-1]:.1f}",
            "[green]yes[/]" if r.passed else "[red]NO[/]",
        )  # fmt: skip
    console.print(table)

    combined = GateResult(
        gate="G1",
        passed=all(r.passed for r in runs.values()),
        metric=min(r.metric for r in runs.values()),  # worst run
        threshold=cfg["threshold"],
        details={
            "metric_is": "minimum Spearman rho across runs",
            "run_dir": str(run_dir),
            "runs": {k: r.as_dict() for k, r in runs.items()},
        },
    )
    write_json(gates_dir / "G1.json", combined.as_dict())
    write_json(run_dir / "G1.json", combined.as_dict())
    console.print(f"G1 {'PASSED' if combined.passed else 'FAILED'} -> {gates_dir / 'G1.json'}")
    return combined.passed
