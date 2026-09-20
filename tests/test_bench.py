"""Latency bench (PREREG §8): warm-up kept apart, failures excluded, resumable; H5 arithmetic."""

import json

import numpy as np
from rich.console import Console

from flight_or_bite.arbiters.jev_arbiter import JevArbiter, load_prompt
from flight_or_bite.arbiters.jev_client import JevHTTPError, MockJevClient
from flight_or_bite.timing import bench
from flight_or_bite.validation.confirm_h5 import boot_delta, delta, points

console = Console(quiet=True)


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines()]


def test_warmup_is_kept_apart_and_a_rerun_only_adds_what_is_missing(tmp_path):
    arbiter = JevArbiter(MockJevClient(latency_s=0.003), load_prompt("naive"))
    path = bench.bench_one(console, arbiter, 5, 2, 1, tmp_path)
    assert [r["warmup"] for r in rows(path)] == [True, True] + [False] * 5
    assert [r["cold"] for r in rows(path)][:2] == [True, False]
    bench.bench_one(console, arbiter, 8, 2, 1, tmp_path)  # resumed: a fresh warm-up, then 3 more
    assert sum(not r["warmup"] for r in rows(path)) == 8
    bench.bench_one(console, arbiter, 8, 2, 1, tmp_path)  # complete: nothing is added
    assert len(rows(path)) == 12
    s = bench.summary(tmp_path)["arbiters"]["jev_naive"]
    assert s["n"] == 8 and 3.0 <= s["p50_ms"] < 4.0 and len(s["cold_ms"]) == 2 and s["valid"]


def test_a_failed_call_is_recorded_and_excluded(tmp_path, monkeypatch):
    client = MockJevClient()
    real, calls = client.evaluate, []

    def flaky(state, questions):
        calls.append(1)
        if len(calls) % 2 == 0:
            raise JevHTTPError(503, "unavailable", None)
        return real(state, questions)

    monkeypatch.setattr(client, "evaluate", flaky)
    path = bench.bench_one(console, JevArbiter(client, load_prompt("naive")), 10, 0, 1, tmp_path)
    assert sum(not r["ok"] for r in rows(path)) == 5
    s = bench.summary(tmp_path)["arbiters"]["jev_naive"]
    assert s["n"] == 5 and s["failed"] == 5 and not s["valid"]  # 50% failures > max_error_share


def test_states_cycle_through_grid_b_in_a_fixed_shuffled_order():
    a, b = bench.states(7), bench.states(7)
    first = [next(a) for _ in range(1225)]
    assert first == [next(b) for _ in range(1225)] and len(set(first)) == 1225
    assert next(a) == first[0]


def test_h5_delta_and_bootstrap():
    c = {"looming_levels": 3, "sugar": [0.0, 0.6]}
    assert [k for k, _, _ in points(c)] == list(range(6)) and points(c)[4] == (4, 0.6, 0.5)
    p = np.array([0.0, 0.5, 1.0, 0.0, 0.2, 1.0])  # sugar 0 | sugar 0.6
    assert np.isclose(delta(p, 3), -0.1)
    samples = np.repeat(p[:, None], 4, axis=1)  # no spread over repeats -> a degenerate bootstrap
    assert np.allclose(boot_delta(samples, 3, 50, np.random.default_rng(0)), -0.1)
