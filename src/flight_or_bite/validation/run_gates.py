"""`fob gate` / `fob gates`: run the formal gates, write reports/gates/<gate>.json and gates.md."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from flight_or_bite.lif.encoding import load_encoding
from flight_or_bite.lif.params import load_params
from flight_or_bite.runlog import start_run, write_json
from flight_or_bite.validation.gates_m3 import load_cfg, run_gate

GATES = ("G1", "G2", "G3", "G4", "G5", "G6", "G7")
TITLES = {"G1": "sugar -> MN9", "G2": "bitter suppresses sugar", "G3": "looming -> DNp01",
          "G4": "real vs shuffled", "G5": "ablations", "G6": "robustness", "G7": "conflict vs independent race"}  # fmt: skip
GATES_DIR = Path(os.environ.get("FOB_GATES_DIR", "reports/gates"))


def run(console: Console, names: list[str]) -> bool:
    run_dir = start_run("gates", {"gates": names, "protocol": load_cfg(), "lif": load_params().model_dump(),
                                  "encoding": load_encoding().model_dump()})  # fmt: skip
    for name in names:
        console.print(f"running {name}: {TITLES[name]} ...")
        result = run_gate(name).as_dict() | {"generated": datetime.now().astimezone().isoformat(timespec="seconds"),
                                             "run_dir": str(run_dir)}  # fmt: skip
        write_json(GATES_DIR / f"{name}.json", result)
        write_json(run_dir / f"{name}.json", result)
        console.print(
            f"  {name}: {'PASSED' if result['passed'] else 'FAILED'} (metric {result['metric']:.4g}, threshold {result['threshold']:.4g})"
        )
    return summary(console)


def summary(console: Console) -> bool:
    table = Table(title="Validity gates (SPEC §5)")
    for col in ("gate", "what", "metric", "threshold", "passed"):
        table.add_column(col)
    ok = True
    for name in GATES:
        path = GATES_DIR / f"{name}.json"
        if not path.is_file():
            table.add_row(name, TITLES[name], "-", "-", "not run")
            ok = False
            continue
        r = json.loads(path.read_text())
        ok &= bool(r["passed"])
        table.add_row(name, TITLES[name], f"{r['metric']:.4g}", f"{r['threshold']:.4g}",
                      "[green]yes[/]" if r["passed"] else "[red]NO[/]")  # fmt: skip
    console.print(table)
    return ok
