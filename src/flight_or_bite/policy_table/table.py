"""Policy tables (SPEC §4.5): pi(action | sugar, bitter, looming, hunger) and latency samples on
a grid; resumable parquet shards; linear interpolation with renormalisation; latency drawn from
the nearest node."""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict

from flight_or_bite.arbiters.base import ACTIONS
from flight_or_bite.types import Action, Arbiter, Decision, Observation

AXES = ("sugar", "bitter", "looming", "hunger")


class GridSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    axes: dict[str, list[float]]
    n_rep: int
    shard_points: int
    seed_base: int

    def model_post_init(self, _: Any) -> None:
        if tuple(self.axes) != AXES:
            raise ValueError(f"axes must be exactly {AXES}, in this order")
        for name, values in self.axes.items():
            if len(values) < 2 or values != sorted(set(values)) or values[0] < 0 or values[-1] > 1:
                raise ValueError(f"axis {name} must be strictly increasing within [0, 1]")

    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(len(self.axes[a]) for a in AXES)

    def points(self) -> list[tuple[int, ...]]:
        return list(itertools.product(*(range(n) for n in self.shape)))

    def observation(self, index: tuple[int, ...]) -> Observation:
        return Observation(**{a: self.axes[a][i] for a, i in zip(AXES, index, strict=True)})


def load_grid(path: Path = Path("configs/grid.yaml")) -> GridSpec:
    return GridSpec.model_validate(yaml.safe_load(path.read_text()))


def _shard_path(out_dir: Path, k: int) -> Path:
    return out_dir / f"shard_{k:04d}.parquet"


def build_table(arbiter: Arbiter, grid: GridSpec, out_dir: Path, on_point=lambda done, total: None,
                key_fn=None) -> int:  # fmt: skip
    """Evaluate `arbiter` n_rep times at every grid point. Resumable: complete shards are kept.

    Returns the number of decisions made in this call. Each (point, repeat) has its own RNG
    stream, so a resumed build is identical to an uninterrupted one for seeded arbiters.

    `key_fn(obs)`: grid points with equal keys produce byte-identical requests (the bucketed Jev
    modes), so only the first point of each key is queried; the others receive copies of its
    repeats, flagged `cache_hit` (never used for latency) with `source_point` naming the origin.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "grid.json").write_text(json.dumps(grid.model_dump(), indent=2))
    points = grid.points()
    made = 0
    first_of_key: dict = {}
    shared: dict[int, list[dict]] = {}
    if key_fn is not None:
        for n, index in enumerate(points):
            first_of_key.setdefault(key_fn(grid.observation(index)), n)

    def rows_of(source: int) -> list[dict]:
        if source not in shared:  # its shard was written by an earlier, interrupted run
            done = pd.read_parquet(_shard_path(out_dir, source // grid.shard_points))
            mask = ~done["cache_hit"]
            for a, i in zip(AXES, points[source], strict=True):
                mask &= done[f"i_{a}"] == i
            shared[source] = done[mask].to_dict("records")
        return shared[source]

    for k, start in enumerate(range(0, len(points), grid.shard_points)):
        chunk = points[start : start + grid.shard_points]
        path = _shard_path(out_dir, k)
        if (
            path.is_file()
            and len(pd.read_parquet(path, columns=["rep"])) == len(chunk) * grid.n_rep
        ):
            on_point(start + len(chunk), len(points))
            continue
        rows = []
        for offset, index in enumerate(chunk):
            obs = grid.observation(index)
            here = start + offset
            source = first_of_key[key_fn(obs)] if key_fn is not None else here
            if source != here:  # an identical request was already made for `source`
                where = {f"i_{a}": i for a, i in zip(AXES, index, strict=True)}
                rows += [
                    {**row, **where, "cache_hit": True, "source_point": source}
                    for row in rows_of(source)
                ]
                on_point(here + 1, len(points))
                continue
            own = []
            for rep in range(grid.n_rep):
                rng = np.random.default_rng([grid.seed_base, here, rep])
                d: Decision = arbiter.decide(obs, rng)
                made += 1
                own.append({
                    **{f"i_{a}": i for a, i in zip(AXES, index, strict=True)},
                    "rep": rep, "action": d.action.value,
                    **{f"p_{a.value.lower()}": d.probs.get(a, 0.0) for a in ACTIONS},
                    "t_wall_ns": d.t_wall_ns, "t_sim_ms": d.t_sim_ms,
                    "cache_hit": bool(d.meta.get("cache_hit", False)),
                    "source_point": here,
                    "meta": json.dumps(d.meta, default=str),
                })  # fmt: skip
            rows += own
            shared[here] = own
            on_point(here + 1, len(points))
        tmp = path.with_suffix(".part")
        pd.DataFrame(rows).to_parquet(tmp)
        tmp.replace(path)  # a shard is either complete or absent
    return made


@dataclass
class PolicyTable:
    grid: GridSpec
    probs: np.ndarray  # [*grid.shape, 3], mean over repeats of the per-repeat probabilities
    latency: dict[tuple[int, ...], pd.DataFrame]  # node -> rows (action, t_wall_ns, t_sim_ms)

    @classmethod
    def load(cls, directory: Path) -> PolicyTable:
        grid = GridSpec.model_validate(json.loads((directory / "grid.json").read_text()))
        shards = sorted(directory.glob("shard_*.parquet"))
        df = pd.concat([pd.read_parquet(s) for s in shards], ignore_index=True)
        expected = int(np.prod(grid.shape)) * grid.n_rep
        if len(df) != expected:
            raise ValueError(f"table is incomplete: {len(df)} of {expected} rows in {directory}")
        keys = [f"i_{a}" for a in AXES]
        probs = np.zeros((*grid.shape, len(ACTIONS)))
        mean = df.groupby(keys)[[f"p_{a.value.lower()}" for a in ACTIONS]].mean()
        for index, row in mean.iterrows():
            probs[index] = row.to_numpy() / row.to_numpy().sum()
        # latency never includes cache hits (SPEC §4.3)
        timed = df[~df["cache_hit"]]
        latency = {index: g[["action", "t_wall_ns", "t_sim_ms"]].reset_index(drop=True)
                   for index, g in timed.groupby(keys)}  # fmt: skip
        points = grid.points()
        for index, g in df.groupby(keys):  # a node made only of copies borrows its source's samples
            if index not in latency and "source_point" in g:
                latency[index] = latency[points[int(g["source_point"].iloc[0])]]
        return cls(grid, probs, latency)

    def _cell(self, axis: str, value: float) -> tuple[int, float]:
        nodes = np.asarray(self.grid.axes[axis])
        v = float(np.clip(value, nodes[0], nodes[-1]))
        lo = int(np.clip(np.searchsorted(nodes, v, side="right") - 1, 0, len(nodes) - 2))
        return lo, (v - nodes[lo]) / (nodes[lo + 1] - nodes[lo])

    def interpolate(self, obs: Observation) -> dict[Action, float]:
        """Multilinear interpolation over the 16 surrounding nodes, renormalised to sum to 1."""
        cells = [self._cell(a, getattr(obs, a)) for a in AXES]
        p = np.zeros(len(ACTIONS))
        for corner in itertools.product((0, 1), repeat=len(AXES)):
            weight = np.prod([w if c else 1.0 - w for c, (_, w) in zip(corner, cells, strict=True)])
            if weight:
                p += (
                    weight
                    * self.probs[tuple(lo + c for c, (lo, _) in zip(corner, cells, strict=True))]
                )
        p = p / p.sum()
        return {a: float(x) for a, x in zip(ACTIONS, p, strict=True)}

    def nearest_node(self, obs: Observation) -> tuple[int, ...]:
        return tuple(
            int(np.abs(np.asarray(self.grid.axes[a]) - getattr(obs, a)).argmin()) for a in AXES
        )

    def sample_latency(
        self, obs: Observation, action: Action, rng: np.random.Generator
    ) -> tuple[int, float | None]:
        """(t_wall_ns, t_sim_ms) of one recorded repeat at the nearest node, with the same outcome
        if that node ever produced it, otherwise any repeat of that node."""
        rows = self.latency[self.nearest_node(obs)]
        same = rows[rows["action"] == action.value]
        pick = (same if len(same) else rows).iloc[
            int(rng.integers(len(same) if len(same) else len(rows)))
        ]
        t_sim = pick["t_sim_ms"]
        return int(pick["t_wall_ns"]), (None if pd.isna(t_sim) else float(t_sim))


class TabularArbiter:
    """Samples decisions and their latency from a table instead of running the arbiter (SPEC §2).
    `t_wall_ns` / `t_sim_ms` are the recorded values, not the cost of the table lookup."""

    def __init__(self, name: str, table: PolicyTable) -> None:
        self.name = name
        self.table = table

    def decide(self, obs: Observation, rng: np.random.Generator) -> Decision:
        probs = self.table.interpolate(obs)
        action = ACTIONS[int(rng.choice(len(ACTIONS), p=[probs[a] for a in ACTIONS]))]
        t_wall_ns, t_sim_ms = self.table.sample_latency(obs, action, rng)
        return Decision(probs=probs, action=action, t_wall_ns=t_wall_ns, t_sim_ms=t_sim_ms,
                        meta={"tabular": True, "node": self.table.nearest_node(obs)})  # fmt: skip
