"""`fob eval`: arbiters on a seed split -> table with confidence intervals (SPEC §7, §9)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

from flight_or_bite.arbiters.baselines import FixedPriorityArbiter, RandomArbiter
from flight_or_bite.arbiters.oracle import OracleArbiter
from flight_or_bite.arena.env import (
    CAUSE_CENSORED,
    EnvConfig,
    check_split_access,
    load_env_config,
)
from flight_or_bite.eval.episodes import EpisodeResult, run_split
from flight_or_bite.eval.stats import bootstrap_mean_ci, paired_bootstrap, percent_of_oracle
from flight_or_bite.runlog import start_run, write_json
from flight_or_bite.types import Arbiter

DEADLINES_MS = (1, 3, 10, 30, 100, 300, 1000, 3000)  # SPEC §6.3-D
CAUSES = ("predator", "starvation", "toxin", "missed_deadline", CAUSE_CENSORED)
BOOTSTRAP_SEED = 20260920
MIN_GAP_TO_FIXED = 0.10  # SPEC §11, M2: below this, propose changing the environment


def default_arbiters(cfg: EnvConfig) -> list[Arbiter]:
    return [RandomArbiter(), FixedPriorityArbiter(), OracleArbiter(cfg)]


def summarise(results: dict[str, list[EpisodeResult]], rng: np.random.Generator) -> dict[str, Any]:
    life = {name: np.array([r.lifetime for r in rs], dtype=float) for name, rs in results.items()}
    rows = {}
    for name, rs in results.items():
        lo, hi = bootstrap_mean_ci(life[name], rng)
        causes = Counter(r.cause for r in rs)
        rows[name] = {
            "episodes": len(rs),
            "lifetime_mean": float(life[name].mean()),
            "lifetime_ci95": [lo, hi],
            "lifetime_median": float(np.median(life[name])),
            "percent_of_oracle": (
                percent_of_oracle(life[name].mean(), life["random"].mean(), life["oracle"].mean())
                if {"random", "oracle"} <= set(life) else None
            ),
            "causes": {c: causes.get(c, 0) / len(rs) for c in CAUSES},
            "mean_energy": float(np.mean([r.mean_energy for r in rs])),
            "final_energy_mean": float(np.mean([r.final_energy for r in rs])),
            "actions": {k: float(np.mean([getattr(r, f"n_{k}") / max(r.n_eat + r.n_escape + r.n_idle, 1)
                                         for r in rs])) for k in ("eat", "escape", "idle")},
            "t_wall_us_median": float(np.median([r.t_wall_ns_median for r in rs]) / 1e3),
        }  # fmt: skip
    names = list(results)
    pairs = {}
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            d = paired_bootstrap(life[b], life[a], rng)
            pairs[f"{b} - {a}"] = {"mean_diff": d.mean_diff, "ci95": [d.ci_low, d.ci_high],
                                   "significant": d.significant}  # fmt: skip
    return {"arbiters": rows, "paired_differences": pairs}


def deadline_sweep(cfg: EnvConfig, arbiters: list[Arbiter], seeds: range, unlock_test: bool,
                   console: Console) -> dict[str, Any]:  # fmt: skip
    out: dict[str, Any] = {}
    for clock in ("wall", "native"):
        out[clock] = {}
        for deadline in DEADLINES_MS:
            timed = cfg.model_copy(update={"deadline_ms": float(deadline)})
            out[clock][deadline] = {
                arb.name: float(np.mean([r.lifetime for r in run_split(
                    timed, arb, seeds, unlock_test=unlock_test, clock=clock)]))
                for arb in arbiters
            }  # fmt: skip
            console.print(f"  deadline {deadline} ms ({clock} track): {out[clock][deadline]}")
    return out


def run_eval(console: Console, split: str, unlock_test: bool, sweep: bool) -> None:
    cfg = load_env_config()
    check_split_access(cfg, split, unlock_test)
    seeds = cfg.seeds_of(split)
    arbiters = default_arbiters(cfg)
    run_dir = start_run(f"eval-{split}", {"env": cfg.model_dump(), "split": split,
                                          "arbiters": [a.name for a in arbiters], "sweep": sweep},
                        seeds={"first": seeds[0], "last": seeds[-1]})  # fmt: skip
    results = {}
    for arb in arbiters:
        console.print(f"running {arb.name} on {len(seeds)} {split} episodes ...")
        results[arb.name] = run_split(cfg, arb, seeds, unlock_test=unlock_test)
    pd.DataFrame([r.as_dict() for rs in results.values() for r in rs]).to_parquet(
        run_dir / "episodes.parquet"
    )
    summary = summarise(results, np.random.default_rng(BOOTSTRAP_SEED))
    summary.update(split=split, episodes=len(seeds), run_dir=str(run_dir),
                   generated=datetime.now().astimezone().isoformat(timespec="seconds"))  # fmt: skip
    if sweep:
        summary["deadline_sweep"] = deadline_sweep(cfg, arbiters, seeds, unlock_test, console)
    rows = summary["arbiters"]
    if {"oracle", "fixed_priority"} <= set(rows):
        gap = 1.0 - rows["fixed_priority"]["lifetime_mean"] / rows["oracle"]["lifetime_mean"]
        summary["oracle_gap_to_fixed_priority"] = gap
        summary["gap_below_threshold"] = gap < MIN_GAP_TO_FIXED
    write_json(run_dir / "summary.json", summary)
    out = Path(f"reports/eval_{split}.md")
    out.write_text(render(summary))

    table = Table(
        title=f"Mean lifetime, {split} split, {len(seeds)} episodes (censored at {cfg.max_trials})"
    )
    for col in ("arbiter", "lifetime [95% CI]", "% of oracle", "predator", "starvation", "toxin",
                "censored", "mean energy"):  # fmt: skip
        table.add_column(col)
    for name, r in rows.items():
        c = r["causes"]
        table.add_row(
            name, f"{r['lifetime_mean']:.1f} [{r['lifetime_ci95'][0]:.1f}, {r['lifetime_ci95'][1]:.1f}]",
            "-" if r["percent_of_oracle"] is None else f"{r['percent_of_oracle']:.0%}",
            f"{c['predator']:.0%}", f"{c['starvation']:.0%}", f"{c['toxin']:.0%}",
            f"{c[CAUSE_CENSORED]:.0%}", f"{r['mean_energy']:.1f}",
        )  # fmt: skip
    console.print(table)
    console.print(f"[green]wrote {out}[/] (episodes: {run_dir / 'episodes.parquet'})")


def render(s: dict[str, Any]) -> str:
    lines = [
        f"# Evaluation on the `{s['split']}` split",
        "",
        f"Generated {s['generated']} by `fob eval --split {s['split']}`; {s['episodes']} episodes, "
        f"paired on seeds; raw data in `{s['run_dir']}`. Bootstrap: 10 000 resamples over episodes.",
        "Lifetime = trials completed alive, censored at the episode limit. No deadline.",
        "",
        "| Arbiter | Mean lifetime [95% CI] | Median | % of oracle | Mean energy | Final energy | "
        "EAT / ESCAPE / IDLE share | t_wall p50, µs |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, r in s["arbiters"].items():
        pct = "—" if r["percent_of_oracle"] is None else f"{r['percent_of_oracle']:.1%}"
        a = r["actions"]
        lines.append(
            f"| `{name}` | {r['lifetime_mean']:.1f} [{r['lifetime_ci95'][0]:.1f}, "
            f"{r['lifetime_ci95'][1]:.1f}] | {r['lifetime_median']:.0f} | {pct} | "
            f"{r['mean_energy']:.1f} | {r['final_energy_mean']:.1f} | "
            f"{a['eat']:.0%} / {a['escape']:.0%} / {a['idle']:.0%} | {r['t_wall_us_median']:.1f} |"
        )
    lines += ["", "Causes of death (share of episodes):", "",
              "| Arbiter | predator | starvation | toxin | missed deadline | censored (alive) |",
              "|---|---|---|---|---|---|"]  # fmt: skip
    for name, r in s["arbiters"].items():
        c = r["causes"]
        lines.append(f"| `{name}` | {c['predator']:.1%} | {c['starvation']:.1%} | {c['toxin']:.1%} | "
                     f"{c['missed_deadline']:.1%} | {c[CAUSE_CENSORED]:.1%} |")  # fmt: skip
    lines += ["", "Paired differences in mean lifetime (a win only if the CI excludes zero):", "",
              "| Comparison | Difference | 95% CI | Significant |", "|---|---|---|---|"]  # fmt: skip
    for name, d in s["paired_differences"].items():
        lines.append(f"| {name} | {d['mean_diff']:+.1f} | [{d['ci95'][0]:+.1f}, {d['ci95'][1]:+.1f}] | "
                     f"{'yes' if d['significant'] else 'no'} |")  # fmt: skip
    if "oracle_gap_to_fixed_priority" in s:
        gap = s["oracle_gap_to_fixed_priority"]
        lines += ["", f"Oracle's margin over `fixed_priority`: **{gap:.1%}** of the oracle's lifetime "
                      f"(SPEC §11 asks for a proposal to change the environment if it is below "
                      f"{MIN_GAP_TO_FIXED:.0%}: {'BELOW' if s['gap_below_threshold'] else 'not the case'})."]  # fmt: skip
    if "deadline_sweep" in s:
        for clock, table in s["deadline_sweep"].items():
            names = list(next(iter(table.values())))
            lines += ["", f"Deadline sweep, `{clock}` track — mean lifetime:", "",
                      "| deadline, ms | " + " | ".join(f"`{n}`" for n in names) + " |",
                      "|---|" + "---|" * len(names)]  # fmt: skip
            for deadline, row in table.items():
                lines.append(f"| {deadline} | " + " | ".join(f"{row[n]:.1f}" for n in names) + " |")
    return "\n".join(lines) + "\n"
