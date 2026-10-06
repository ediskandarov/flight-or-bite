"""Full additional TypeSafe latency benchmark; run from the repository root on AC power.

Preserves reports/latency (OpenRouter), resumes in reports/latency_typesafe,
and uses exactly the existing JevArbiter + bench_one timing path.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values
from rich.console import Console

from flight_or_bite import prereg
from flight_or_bite.arbiters.jev_arbiter import JevArbiter, load_prompt, prompt_hash
from flight_or_bite.arbiters.typesafe_client import MODEL, TypeSafeClient
from flight_or_bite.lif.perf import throttle_check
from flight_or_bite.runlog import start_run, write_json
from flight_or_bite.timing import bench
from flight_or_bite.timing.typesafe_spend import update_spend

OUT = Path("reports/latency_typesafe")
ORIGINAL = Path("reports/latency")


def compare(out, original, cfg):
    direct, prior = bench.summary(out), bench.summary(original)
    complete = all(direct["arbiters"].get(f"jev_{mode}", {}).get("attempts") == cfg["n"]
                   for mode in cfg["jev_modes"])
    lines = ["# Jev: OpenRouter vs direct TypeSafe (additional analysis)", "",
             f"Direct collection complete: {complete}. Updated {datetime.now().astimezone().isoformat(timespec='seconds')}.",
             "Same prompt versions, state sequence, warm-up and JevArbiter timer; different run times.",
             "Both times include network. Snapshot identity across provider model IDs is not verified.",
             "The original preregistered experiment is unchanged; this comparison was requested after its results.", "",
             "| Mode | OpenRouter n | direct n | OpenRouter p50 / p95 ms | direct p50 / p95 ms | direct valid (errors) |",
             "|---|---:|---:|---:|---:|---|"]
    for mode in cfg["jev_modes"]:
        name = f"jev_{mode}"
        a, b = prior["arbiters"].get(name), direct["arbiters"].get(name)
        if not a or not b:
            lines.append(f"| {mode} | — | — | — | — | missing |")
            continue
        lines.append(f"| {mode} | {a['n']} | {b['n']} | {a['p50_ms']:.3f} / {a['p95_ms']:.3f} | "
                     f"{b['p50_ms']:.3f} / {b['p95_ms']:.3f} | {b['valid']} |")
    lines += ["", "Power/timer checks and individual run records: `bench_meta.json`.",
              "Cost estimate (including warm-up, probes and failed attempts): `../direct_typesafe/spend.json`."]
    (out / "comparison.md").write_text("\n".join(lines) + "\n")


def run(console, out=OUT, original=ORIGINAL, client_factory=TypeSafeClient):
    if out.resolve() == original.resolve() or original.resolve() in out.resolve().parents:
        raise ValueError("Refusing to write into the preserved OpenRouter directory")
    prereg.check()
    cfg = bench.load_cfg()
    protocol = {"provider": "typesafe-direct", "model": MODEL, "timing": cfg,
                "prompts": {m: prompt_hash(m) for m in cfg["jev_modes"]}}
    identity = out / "protocol.json"
    if identity.is_file():
        if json.loads(identity.read_text()) != protocol:
            raise ValueError("Existing direct benchmark protocol differs; cannot mix results")
    elif out.exists() and any(out.iterdir()):
        raise ValueError("Output is nonempty without a protocol; refusing to mix results")
    check = throttle_check()
    console.print(f"throttle check: {check}")
    if check["timer_throttled"] or "AC Power" not in check["power"]:
        raise RuntimeError("Benchmark not started: connect AC power and resolve timer throttling (D5)")
    write_json(identity, protocol)
    run_dir = start_run("latency-typesafe", {"protocol": protocol, "throttle": check, "out": str(out)})
    meta_path = out / "bench_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"runs": []}
    entry = {"run_dir": str(run_dir), "provider": "typesafe-direct", "throttle": check, "status": "running"}
    meta["runs"].append(entry)
    write_json(meta_path, meta)
    try:
        for mode in cfg["jev_modes"]:
            with client_factory(log_dir=out / "raw" / mode) as client:
                bench.bench_one(console, JevArbiter(client, load_prompt(mode), retries=0), cfg["n"],
                                cfg["warmup"], cfg["state_seed"], out)
            update_spend(bench_root=out)
        entry["status"] = "completed"
    except BaseException as exc:
        entry.update(status="interrupted", error_type=type(exc).__name__)
        raise
    finally:
        write_json(meta_path, meta)
        update_spend(bench_root=out)
        compare(out, original, cfg)
    console.print(bench.render(bench.summary(out)))
    console.print(f"Comparison: {out / 'comparison.md'}")


if __name__ == "__main__":
    key = os.environ.get("TYPESAFE_API_KEY") or dotenv_values(".env").get("TYPESAFE_API_KEY")
    if not key:
        raise SystemExit("TYPESAFE_API_KEY is missing")
    os.environ["TYPESAFE_API_KEY"] = key.strip()
    run(Console())
