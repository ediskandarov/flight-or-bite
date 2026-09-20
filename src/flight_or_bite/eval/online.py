"""Main metric (PREREG §2): paired ONLINE episodes with native actions, resumable.

Episodes are played seed by seed, every arbiter on the same seed, so an interrupted run leaves
paired data. An episode is written only when it has finished; if Jev cannot deliver a decision
(PREREG §2b) the run stops, the unfinished episode is discarded, and the next invocation
replays it from its start on the same seed.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from rich.console import Console

from flight_or_bite.arbiters.baselines import FixedPriorityArbiter, RandomArbiter
from flight_or_bite.arbiters.jev_client import JevError
from flight_or_bite.arbiters.oracle import OracleArbiter
from flight_or_bite.arena.env import Arena, EnvConfig, check_split_access, load_env_config
from flight_or_bite.eval.episodes import EpisodeResult, arbiter_rng
from flight_or_bite.runlog import start_run
from flight_or_bite.types import Action, Arbiter

MAIN_JEV_MODE = "informed"  # PREREG §2a
ARBITERS = ("connectome", f"jev_{MAIN_JEV_MODE}", "oracle", "fixed_priority", "random")


class RunStopped(Exception):
    pass


def make_arbiter(name: str, cfg: EnvConfig, *, sample: bool, mock_jev: bool = False) -> Arbiter:
    if name == "connectome":
        from flight_or_bite.arbiters.connectome import ConnectomeArbiter

        return ConnectomeArbiter()
    if name.startswith("jev_"):
        from flight_or_bite.arbiters.jev_arbiter import JevArbiter, load_prompt
        from flight_or_bite.arbiters.jev_client import JevClient, MockJevClient

        client = MockJevClient() if mock_jev else JevClient()
        arbiter = JevArbiter(client, load_prompt(name.removeprefix("jev_")), retries=5)
    else:
        arbiter = {"oracle": lambda: OracleArbiter(cfg), "fixed_priority": FixedPriorityArbiter,
                   "random": RandomArbiter}[name]()  # fmt: skip
    arbiter.sample_from_probs = sample
    return arbiter


def _done(path: Path) -> set[tuple[str, int]]:
    if not path.is_file():
        return set()
    return {(r["arbiter"], r["seed"]) for r in map(json.loads, path.read_text().splitlines())}


def play(arena: Arena, arbiter: Arbiter, seed: int) -> tuple[EpisodeResult, list[dict]]:
    obs, rng = arena.reset(seed), arbiter_rng(seed, arbiter.name)
    counts, energies, decisions = Counter(), [], []
    done, info = False, {}
    while not done:
        energies.append((1.0 - obs.hunger) * arena.cfg.energy_max)
        d = arbiter.decide(obs, rng)
        decisions.append({
            "arbiter": arbiter.name, "seed": seed, "trial": len(decisions), "action": d.action.value,
            "t_wall_ns": d.t_wall_ns, "t_sim_ms": d.t_sim_ms, "retried": int(d.meta.get("retried", 0)),
            **{f"p_{a.value.lower()}": d.probs.get(a, 0.0) for a in Action},
            "sugar": obs.sugar, "bitter": obs.bitter, "looming": obs.looming, "hunger": obs.hunger,
        })  # fmt: skip
        obs, done, info = arena.step(d.action)
        counts[info["action"]] += 1
    walls = [x["t_wall_ns"] for x in decisions]
    return EpisodeResult(
        arbiter=arbiter.name, seed=seed, lifetime=info["lifetime"], cause=info["cause"],
        final_energy=info["energy"], mean_energy=float(np.mean(energies)),
        n_eat=counts[Action.EAT], n_escape=counts[Action.ESCAPE], n_idle=counts[Action.IDLE],
        n_missed_deadline=0, t_wall_ns_median=float(np.median(walls)),
    ), decisions  # fmt: skip


def run_online(console: Console, split: str, episodes: int | None, unlock_test: bool, sample: bool,
               out: Path | None, names: tuple[str, ...] = ARBITERS, mock_jev: bool = False) -> Path:  # fmt: skip
    cfg = load_env_config()
    check_split_access(cfg, split, unlock_test)
    seeds = list(cfg.seeds_of(split))[: episodes or (100 if sample else 300)]
    out = out or Path("reports/online") / (f"{split}_sampled" if sample else split)
    out.mkdir(parents=True, exist_ok=True)
    ep_path, dec_path, stop_path = (
        out / "episodes.jsonl",
        out / "decisions.jsonl",
        out / "stops.jsonl",
    )
    finished = _done(ep_path)
    start_run(f"online-{split}", {"env": cfg.model_dump(), "arbiters": names, "sample": sample,
                                  "episodes": len(seeds), "out": str(out), "resumed": len(finished)},
              seeds={"first": seeds[0], "last": seeds[-1]})  # fmt: skip
    arbiters = {n: make_arbiter(n, cfg, sample=sample, mock_jev=mock_jev) for n in names}
    arena = Arena(cfg, unlock_test=unlock_test)
    console.print(f"online {split}: {len(seeds)} episodes x {len(names)} arbiters; "
                  f"{len(finished)} episode(s) already done -> {out}")  # fmt: skip
    for k, seed in enumerate(seeds):
        for name, arbiter in arbiters.items():
            if (arbiter.name, seed) in finished:
                continue
            try:
                result, decisions = play(arena, arbiter, seed)
            except (JevError, httpx.TransportError) as e:
                stop = {"ts": datetime.now().astimezone().isoformat(timespec="seconds"), "arbiter": name,
                        "seed": seed, "error": f"{type(e).__name__}: {e}"[:500]}  # fmt: skip
                with stop_path.open("a") as f:
                    f.write(json.dumps(stop) + "\n")
                raise RunStopped(f"stopped at seed {seed}, arbiter {name}: {stop['error']}. The unfinished "
                                 "episode was discarded; re-run the same command to resume.") from e  # fmt: skip
            with dec_path.open("a") as f:
                f.writelines(json.dumps(d) + "\n" for d in decisions)
            with ep_path.open("a") as f:  # written last: an episode exists only if it is complete
                f.write(json.dumps(result.as_dict()) + "\n")
        if (k + 1) % 10 == 0 or k + 1 == len(seeds):
            console.print(f"  {k + 1}/{len(seeds)} seeds done")
    return out


def load_episodes(out: Path) -> dict[str, list[EpisodeResult]]:
    rows = [json.loads(line) for line in (out / "episodes.jsonl").read_text().splitlines()]
    by: dict[str, list[EpisodeResult]] = {}
    for r in sorted(rows, key=lambda r: r["seed"]):
        by.setdefault(r["arbiter"], []).append(EpisodeResult(**r))
    return by


def paired_only(by: dict[str, list[EpisodeResult]]) -> dict[str, list[EpisodeResult]]:
    """Keep the seeds every arbiter has finished (an interrupted run stays paired)."""
    common = set.intersection(*({r.seed for r in rs} for rs in by.values()))
    return {n: [r for r in rs if r.seed in common] for n, rs in by.items()}


def summary_of(out: Path) -> dict[str, Any]:
    from flight_or_bite.eval.run_eval import BOOTSTRAP_SEED, summarise

    by = paired_only(load_episodes(out))
    s = summarise(by, np.random.default_rng(BOOTSTRAP_SEED))
    s["episodes"] = len(next(iter(by.values())))
    stops = out / "stops.jsonl"
    s["stops"] = [json.loads(x) for x in stops.read_text().splitlines()] if stops.is_file() else []
    return s
