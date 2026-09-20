"""Policy tables: grid, resumable build, interpolation with renormalisation, latency sampling."""

import numpy as np
import pandas as pd
import pytest

from flight_or_bite.arbiters.base import TimedArbiter
from flight_or_bite.policy_table.table import (
    GridSpec,
    PolicyTable,
    TabularArbiter,
    build_table,
    load_grid,
)
from flight_or_bite.types import Action, Arbiter, Observation

GRID = GridSpec(
    axes={"sugar": [0.0, 1.0], "bitter": [0.0, 1.0], "looming": [0.0, 0.5, 1.0],
          "hunger": [0.0, 1.0]},
    n_rep=4, shard_points=5, seed_base=1,
)  # fmt: skip


class LoomingRamp(TimedArbiter):
    """p_escape = looming, the rest is EAT; reports t_sim = 10 ms for ESCAPE, 40 ms for EAT."""

    name = "ramp"
    calls = 0
    sample_from_probs = True  # a stochastic arbiter: its outcomes vary between repeats

    def policy(self, obs):
        LoomingRamp.calls += 1
        return {Action.ESCAPE: obs.looming, Action.EAT: 1 - obs.looming, Action.IDLE: 0.0}, {}

    def decide(self, obs, rng):
        d = super().decide(obs, rng)
        d.t_sim_ms = 10.0 if d.action is Action.ESCAPE else 40.0
        return d


@pytest.fixture
def table_dir(tmp_path):
    build_table(LoomingRamp(), GRID, tmp_path / "ramp")
    return tmp_path / "ramp"


def test_project_grid_is_grid_b():
    grid = load_grid()
    assert grid.shape == (7, 5, 7, 5) and len(grid.points()) == 1225 and grid.n_rep == 20  # D27


def test_grid_validation():
    with pytest.raises(ValueError):
        GridSpec(axes={"sugar": [0, 1]}, n_rep=1, shard_points=1, seed_base=0)
    with pytest.raises(ValueError):
        GridSpec(axes={**GRID.axes, "hunger": [1.0, 0.0]}, n_rep=1, shard_points=1, seed_base=0)


def test_build_writes_complete_shards_and_resumes(tmp_path):
    out = tmp_path / "t"
    LoomingRamp.calls = 0
    made = build_table(LoomingRamp(), GRID, out)
    assert made == 24 * 4 == LoomingRamp.calls
    shards = sorted(out.glob("shard_*.parquet"))
    assert len(shards) == 5 and not list(out.glob("*.part"))
    first = pd.read_parquet(shards[0])

    shards[2].unlink()  # simulate an interrupted build
    assert build_table(LoomingRamp(), GRID, out) == 5 * 4  # only the missing shard is redone
    assert build_table(LoomingRamp(), GRID, out) == 0
    again = pd.read_parquet(shards[0])
    assert first[["action", "p_escape"]].equals(again[["action", "p_escape"]])


def test_incomplete_table_is_refused(table_dir):
    sorted(table_dir.glob("shard_*.parquet"))[0].unlink()
    with pytest.raises(ValueError, match="incomplete"):
        PolicyTable.load(table_dir)


def test_interpolation_is_exact_at_nodes_linear_between_and_normalised(table_dir):
    table = PolicyTable.load(table_dir)
    at_node = table.interpolate(Observation(0.0, 1.0, 0.5, 1.0))
    assert at_node[Action.ESCAPE] == pytest.approx(0.5) and at_node[Action.IDLE] == 0.0
    between = table.interpolate(Observation(0.3, 0.7, 0.25, 0.1))
    assert between[Action.ESCAPE] == pytest.approx(0.25) and between[Action.EAT] == pytest.approx(0.75)
    assert sum(between.values()) == pytest.approx(1.0)
    assert table.interpolate(Observation(0.0, 0.0, 1.0, 0.0))[Action.ESCAPE] == pytest.approx(1.0)


def test_renormalisation_handles_rows_that_do_not_sum_to_one(table_dir):
    table = PolicyTable.load(table_dir)
    table.probs *= 0.98  # e.g. an API that rounds probabilities
    p = table.interpolate(Observation(0.5, 0.5, 0.4, 0.5))
    assert sum(p.values()) == pytest.approx(1.0) and p[Action.ESCAPE] == pytest.approx(0.4)


def test_latency_comes_from_the_nearest_node_and_matches_the_outcome(table_dir):
    table = PolicyTable.load(table_dir)
    rng = np.random.default_rng(0)
    obs = Observation(0.1, 0.9, 0.45, 0.2)
    assert table.nearest_node(obs) == (0, 1, 1, 0)
    for _ in range(20):
        assert table.sample_latency(obs, Action.ESCAPE, rng)[1] == 10.0
        assert table.sample_latency(obs, Action.EAT, rng)[1] == 40.0
    # an outcome the node never produced falls back to any repeat of that node
    assert table.sample_latency(obs, Action.IDLE, rng)[1] in (10.0, 40.0)
    never_escapes = Observation(0.0, 0.0, 0.0, 0.0)
    assert table.sample_latency(never_escapes, Action.ESCAPE, rng)[1] == 40.0


def test_cache_hits_never_enter_latency(table_dir):
    shard = sorted(table_dir.glob("shard_*.parquet"))[0]
    df = pd.read_parquet(shard)
    df.loc[df.index[:3], ["cache_hit", "t_wall_ns"]] = [True, 1]
    df.to_parquet(shard)
    table = PolicyTable.load(table_dir)
    assert all((rows["t_wall_ns"] > 1).all() for rows in table.latency.values())


def test_tabular_arbiter_reproduces_the_policy_and_reports_recorded_latency(table_dir):
    arbiter = TabularArbiter("ramp_table", PolicyTable.load(table_dir))
    assert isinstance(arbiter, Arbiter)
    rng = np.random.default_rng(0)
    decisions = [arbiter.decide(Observation(0.5, 0.5, 0.75, 0.5), rng) for _ in range(2000)]
    share = np.mean([d.action is Action.ESCAPE for d in decisions])
    assert share == pytest.approx(0.75, abs=0.03)
    assert all(d.t_sim_ms == (10.0 if d.action is Action.ESCAPE else 40.0) for d in decisions)
    assert decisions[0].meta["tabular"] and decisions[0].probs[Action.ESCAPE] == pytest.approx(0.75)


def test_points_with_identical_requests_are_queried_once(tmp_path):
    """Bucketed Jev modes: here looming 0.0 and 0.5 share a key, 1.0 does not."""
    LoomingRamp.calls = 0

    def key(obs):
        return (obs.sugar, obs.bitter, obs.looming >= 0.75, obs.hunger)

    made = build_table(LoomingRamp(), GRID, tmp_path / "k", key_fn=key)
    assert made == LoomingRamp.calls == 16 * 4  # 8 cells x 2 keys x 4 repeats
    shards = sorted((tmp_path / "k").glob("shard_*.parquet"))
    df = pd.concat(pd.read_parquet(f) for f in shards)
    assert len(df) == 24 * 4 and int(df["cache_hit"].sum()) == 8 * 4
    copies = df[df["cache_hit"]]
    assert (copies["i_looming"] == 1).all() and (copies["p_escape"] == 0.0).all()
    table = PolicyTable.load(tmp_path / "k")
    assert table.interpolate(Observation(0.0, 0.0, 0.5, 0.0))[Action.ESCAPE] == 0.0
    assert len(table.latency[(0, 0, 1, 0)]) == 4  # a copied node borrows its source's samples
    assert build_table(LoomingRamp(), GRID, tmp_path / "k", key_fn=key) == 0  # resumable
