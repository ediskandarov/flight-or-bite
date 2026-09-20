"""Decision-time measurement (PREREG §8; SPEC §6.2 as amended by D10-D15).

Protocol: configs/timing.yaml (hashed in PREREG.md). Run by the human from their own terminal, on
AC power, under `caffeinate -i` (D5); a run from the agent's process is a crash test, not a result.

One file of samples per arbiter, `reports/latency/<arbiter>.jsonl`, one line per decision. The
bench is resumable: a re-run appends until `n` timed attempts exist. Every (re)start of a Jev mode
opens a fresh keep-alive session and repeats the warm-up, because a new connection is cold.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import yaml
from rich.console import Console

from flight_or_bite.arbiters.jev_client import CallBudgetExceeded, JevAuthError, JevError, JevModelMismatch
from flight_or_bite.eval.episodes import arbiter_rng
from flight_or_bite.policy_table.table import load_grid
from flight_or_bite.runlog import start_run, write_json
from flight_or_bite.timing.timers import summarize_ns
from flight_or_bite.types import Arbiter, Observation

OUT = Path("reports/latency")
BASELINES = ("oracle", "fixed_priority", "random")
FATAL = (JevAuthError, CallBudgetExceeded, JevModelMismatch)  # no point in recording 1000 of these


def load_cfg(path: Path = Path("configs/timing.yaml")) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())


def states(seed: int) -> Iterator[Observation]:
    """Grid-B points, shuffled once with `state_seed`, cycled: easy and hard conflicts alike."""
    grid = load_grid()
    points = grid.points()
    order = np.random.default_rng(seed).permutation(len(points))
    while True:
        for k in order:
            yield grid.observation(points[k])


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines()] if path.is_file() else []


def bench_one(console: Console, arbiter: Arbiter, n: int, warmup: int, state_seed: int, out: Path) -> Path:
    path = out / f"{arbiter.name}.jsonl"
    have = sum(1 for r in _rows(path) if not r["warmup"])
    todo = max(0, n - have)
    console.print(f"{arbiter.name}: {have} timed decisions on disk, {todo} to go (+{warmup if todo else 0} warm-up)")
    if not todo:
        return path
    rng, feed = arbiter_rng(state_seed, arbiter.name), states(state_seed)
    for _ in range(have):  # a resumed bench continues through the state cycle
        next(feed)
    out.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for k in range(warmup + todo):
            obs = next(feed) if k >= warmup else Observation(0.5, 0.0, 0.5, 0.5)
            row: dict[str, Any] = {"arbiter": arbiter.name, "warmup": k < warmup, "cold": k == 0 and warmup > 0,
                                   "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                                   "sugar": obs.sugar, "bitter": obs.bitter, "looming": obs.looming,
                                   "hunger": obs.hunger}  # fmt: skip
            try:
                d = arbiter.decide(obs, rng)
                row |= {"ok": True, "action": d.action.value, "t_wall_ns": d.t_wall_ns, "t_sim_ms": d.t_sim_ms,
                        "cache_hit": bool(d.meta.get("cache_hit", False)), "retried": int(d.meta.get("retried", 0)),
                        "model_version": d.meta.get("model_version")}  # fmt: skip
            except FATAL:
                raise
            except (JevError, httpx.TransportError) as e:  # recorded, excluded from the statistics
                row |= {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
            f.write(json.dumps(row) + "\n")
            f.flush()
            if (k + 1 - warmup) % 100 == 0 and k >= warmup:
                console.print(f"  {arbiter.name}: {k + 1 - warmup}/{todo}")
    return path


def run_bench(console: Console, which: str, n: int | None, mock: bool, out: Path = OUT) -> None:
    from flight_or_bite.lif.perf import throttle_check

    cfg = load_cfg()
    n = n or cfg["n"]
    throttle = throttle_check()
    console.print(f"throttle check: {throttle}")
    if throttle["timer_throttled"] or "AC Power" not in throttle["power"]:
        console.print("[yellow]not on AC power or timers are throttled: these numbers are not decision-grade (D5)[/]")
    run_dir = start_run("latency-bench", {"timing": cfg, "which": which, "n": n, "mock": mock, "out": str(out),
                                          "throttle": throttle})  # fmt: skip
    loads: dict[str, float] = {}
    if which in ("jev", "all"):
        from flight_or_bite.arbiters.jev_arbiter import JevArbiter, load_prompt
        from flight_or_bite.arbiters.jev_client import JevClient, MockJevClient

        for mode in cfg["jev_modes"]:  # one keep-alive session per mode; no retries (timing.yaml)
            with MockJevClient(latency_s=0.002) if mock else JevClient() as client:
                bench_one(console, JevArbiter(client, load_prompt(mode), retries=0), n, cfg["warmup"],
                          cfg["state_seed"], out)  # fmt: skip
    if which in ("connectome", "all"):
        from flight_or_bite.arbiters.connectome import ConnectomeArbiter

        arbiter = ConnectomeArbiter()  # one process, graph in memory
        loads["connectome"] = arbiter.t_load_s
        bench_one(console, arbiter, n, 0, cfg["state_seed"], out)
    if which == "all":
        from flight_or_bite.arena.env import load_env_config
        from flight_or_bite.eval.online import make_arbiter

        env = load_env_config()
        for name in BASELINES:
            bench_one(console, make_arbiter(name, env, sample=False), n, 0, cfg["state_seed"], out)
    meta_path = out / "bench_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {"runs": []}
    meta["runs"].append({"run_dir": str(run_dir), "which": which, "n": n, "mock": mock, "throttle": throttle,
                         "t_load_s": loads})  # fmt: skip
    write_json(meta_path, meta)
    console.print(render(summary(out)))


def summary(out: Path = OUT) -> dict[str, Any]:
    cfg = load_cfg()
    arbiters: dict[str, Any] = {}
    for path in sorted(out.glob("*.jsonl")):
        rows = _rows(path)
        timed = [r for r in rows if not r["warmup"]]
        good = [r for r in timed if r["ok"] and not r["cache_hit"] and not r["retried"]]
        if not good:
            continue
        walls = [r["t_wall_ns"] for r in good]
        s = summarize_ns(walls)
        a: dict[str, Any] = {"n": s.n, "attempts": len(timed), "failed": sum(1 for r in timed if not r["ok"]),
                             "p50_ms": s.p50_ms, "p95_ms": s.p95_ms, "mean_ms": s.mean_ms}  # fmt: skip
        a["valid"] = a["failed"] <= cfg["max_error_share"] * max(1, len(timed))
        cold = [r for r in rows if r.get("cold") and r["ok"]]
        if cold:
            a["cold_ms"] = [r["t_wall_ns"] / 1e6 for r in cold]
        sims = [r["t_sim_ms"] for r in good if r["t_sim_ms"] is not None]
        if sims:
            a["t_sim_p50_ms"], a["t_sim_p95_ms"] = (float(x) for x in np.percentile(sims, [50, 95]))
            a["rtf"] = float(sum(sims) / (sum(walls) / 1e6))  # elapsed t_sim / t_wall (SPEC §6.2)
        a["models"] = sorted({r["model_version"] for r in good if r.get("model_version")})
        a["deadline_share_wall"] = {str(d): float(np.mean(np.array(walls) / 1e6 <= d)) for d in cfg["deadlines_ms"]}
        a["hist_log10_ms"] = np.histogram(np.log10(np.array(walls) / 1e6), bins=HIST_BINS)[0].tolist()
        arbiters[path.stem] = a
    meta_path = out / "bench_meta.json"
    return {"arbiters": arbiters, "meta": json.loads(meta_path.read_text()) if meta_path.is_file() else None}


HIST_BINS = np.linspace(-3, 4, 29)  # 1 us .. 10 s, a quarter of a decade per bin; one scale for everybody
BLOCKS = " ▁▂▃▄▅▆▇█"


def _spark(counts: list[int]) -> str:
    top = max(counts) or 1
    return "".join(BLOCKS[int(np.ceil(8 * c / top))] for c in counts)


def render(s: dict[str, Any]) -> str:
    lines = ["| Арбитр | n | t_wall p50, мс | p95, мс | холодный вызов, мс | t_sim p50 / p95, мс | RTF | сбоев | "
             "гистограмма t_wall, 1 мкс … 10 с (лог) |", "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for name, a in s["arbiters"].items():
        cold = ", ".join(f"{x:.0f}" for x in a.get("cold_ms", [])) or "—"
        sim = f"{a['t_sim_p50_ms']:.1f} / {a['t_sim_p95_ms']:.1f}" if "t_sim_p50_ms" in a else "—"
        rtf = f"{a['rtf']:.2f}" if "rtf" in a else "—"
        bad = f"{a['failed']} / {a['attempts']}" + ("" if a["valid"] else " **(замер недействителен)**")
        lines.append(f"| `{name}` | {a['n']} | {a['p50_ms']:.3g} | {a['p95_ms']:.3g} | {cold} | {sim} | {rtf} | "
                     f"{bad} | `{_spark(a['hist_log10_ms'])}` |")  # fmt: skip
    return "\n".join(lines)
