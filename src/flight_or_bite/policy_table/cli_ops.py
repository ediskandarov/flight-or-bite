"""`fob table build`, `fob table show`, `fob replay` (SPEC §9)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from flight_or_bite.arbiters.base import ACTIONS
from flight_or_bite.arena.env import Arena, load_env_config
from flight_or_bite.eval.episodes import arbiter_rng
from flight_or_bite.policy_table.table import (
    AXES,
    PolicyTable,
    SessionTooEarly,
    TabularArbiter,
    build_table,
    check_gap,
    load_grid,
)
from flight_or_bite.types import Arbiter

TABLE_ROOT = Path("reports/tables")
DIRECT = ("random", "fixed_priority", "oracle")


class NotReady(Exception):
    pass


def make_arbiter(name: str, *, mode: str | None = None, mock: bool = False) -> Arbiter:
    cfg = load_env_config()
    if name == "random":
        from flight_or_bite.arbiters.baselines import RandomArbiter

        return RandomArbiter()
    if name == "fixed_priority":
        from flight_or_bite.arbiters.baselines import FixedPriorityArbiter

        return FixedPriorityArbiter()
    if name == "oracle":
        from flight_or_bite.arbiters.oracle import OracleArbiter

        return OracleArbiter(cfg)
    if name == "jev":
        from flight_or_bite.arbiters.jev_arbiter import MODES, JevArbiter, load_prompt
        from flight_or_bite.arbiters.jev_client import JevClient, MockJevClient

        if mode not in MODES:
            raise NotReady(f"--mode is required for jev: one of {', '.join(MODES)}")
        return JevArbiter(MockJevClient() if mock else JevClient(), load_prompt(mode), retries=5)
    if name == "connectome":
        from flight_or_bite.arbiters.connectome import ConnectomeArbiter

        return ConnectomeArbiter()
    raise NotReady(f"tables for {name!r} are not part of the preregistered plan")


def table_dir(name: str, mode: str | None, mock: bool) -> Path:
    label = name if name != "jev" else f"jev_{mode}{'_mock' if mock else ''}"
    return TABLE_ROOT / label


def table_build(console: Console, name: str, mode: str | None, mock: bool, grid_path: Path, session: int = 1) -> None:
    grid = load_grid(grid_path)
    out = table_dir(name, mode, mock)
    n_rep = grid.n_rep
    if name == "jev" and grid.jev is not None:  # PREREG §7: passes of 5 repeats, 12 h apart
        if not 1 <= session <= grid.jev.sessions:
            raise NotReady(f"--session must be 1..{grid.jev.sessions}")
        n_rep = grid.jev.n_rep_per_session
        try:
            check_gap(out, session, 0.0 if mock else grid.jev.min_gap_hours)
        except SessionTooEarly as e:
            raise NotReady(str(e)) from e
    elif session != 1:
        raise NotReady("only Jev tables are built in several sessions")
    arbiter = make_arbiter(name, mode=mode, mock=mock)
    total = len(grid.points())
    prompt = getattr(arbiter, "prompt", None)
    key_fn = prompt.state_key if prompt is not None and prompt.buckets else None  # D47
    with Progress(console=console) as progress:
        task = progress.add_task(f"{arbiter.name}: {total} points x {n_rep}, session {session}", total=total)
        made = build_table(arbiter, grid, out, lambda done, _: progress.update(task, completed=done), key_fn,
                           session=session, n_rep=n_rep)  # fmt: skip
    console.print(f"[green]{out}[/]: {made} new decisions, {total * n_rep} rows in session {session}")


def load_tabular(label: str) -> TabularArbiter:
    directory = TABLE_ROOT / label
    if not (directory / "grid.json").is_file():
        raise NotReady(f"no table at {directory}; build it with `fob table build`")
    return TabularArbiter(f"{label}_table", PolicyTable.load(directory))


def table_show(console: Console, label: str, axis: str, at: dict[str, float]) -> None:
    if axis not in AXES:
        raise NotReady(f"--slice must be one of {', '.join(AXES)}")
    table = load_tabular(label).table
    fixed = {a: at.get(a, table.grid.axes[a][len(table.grid.axes[a]) // 2]) for a in AXES if a != axis}
    nearest = {a: int(np.abs(np.asarray(table.grid.axes[a]) - v).argmin()) for a, v in fixed.items()}
    out = Table(title=f"{label}: slice over {axis} at " + ", ".join(
        f"{a}={table.grid.axes[a][i]}" for a, i in nearest.items()))  # fmt: skip
    for col in (
        axis,
        *(f"p_{a.value.lower()}" for a in ACTIONS),
        "t_wall p50 ms",
        "t_sim p50 ms",
        "n",
    ):
        out.add_column(col, justify="right")
    for i, value in enumerate(table.grid.axes[axis]):
        node = tuple(i if a == axis else nearest[a] for a in AXES)
        rows = table.latency[node]
        t_sim = rows["t_sim_ms"].dropna()
        out.add_row(f"{value:g}", *(f"{p:.3f}" for p in table.probs[node]),
                    f"{np.median(rows['t_wall_ns']) / 1e6:.3f}",
                    f"{np.median(t_sim):.1f}" if len(t_sim) else "-", str(len(rows)))  # fmt: skip
    console.print(out)


def replay(console: Console, seed: int, label: str) -> None:
    cfg = load_env_config()
    arbiter = make_arbiter(label) if label in DIRECT and not (TABLE_ROOT / label).exists() else load_tabular(label)
    arena = Arena(cfg)
    obs, rng = arena.reset(seed), arbiter_rng(seed, arbiter.name)
    console.print(f"replay: arbiter {arbiter.name}, seed {seed} ({cfg.split_of(seed) or 'no split'})")
    done, info = False, {}
    while not done:
        d = arbiter.decide(obs, rng)
        line = (f" t={arena._t:03d}  sugar {obs.sugar:.2f}  bitter {obs.bitter:.2f}  loom {obs.looming:.2f}"
                f"  energy {(1 - obs.hunger) * cfg.energy_max:5.1f}  ->  {d.action.value:6s} "
                + " ".join(f"{a.value[:3]} {d.probs.get(a, 0):.2f}" for a in ACTIONS))  # fmt: skip
        obs, done, info = arena.step(d.action, decision_time_ms=d.t_wall_ns / 1e6)
        flags = ("  THREAT" if info["threat"] else "") + ("  TOXIC" if info["toxic"] else "")
        console.print(line + flags, highlight=False)
    console.print(f"end: {info['cause']} after {info['lifetime']} trials, energy {info['energy']:.1f}")
