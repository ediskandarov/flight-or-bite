"""Core types, timers and host info."""

import time

import pytest

from flight_or_bite import sysinfo
from flight_or_bite.timing.timers import Stopwatch, busy_wait_ns, summarize_ns
from flight_or_bite.types import Action, Arbiter, Decision, Observation


def test_actions_match_spec():
    assert [a.value for a in Action] == ["EAT", "ESCAPE", "IDLE"]


@pytest.mark.parametrize("field", ["sugar", "bitter", "looming", "hunger"])
@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_observation_rejects_out_of_range(field, bad):
    values = {"sugar": 0.5, "bitter": 0.5, "looming": 0.5, "hunger": 0.5, field: bad}
    with pytest.raises(ValueError):
        Observation(**values)


def test_arbiter_protocol_is_structural():
    class Fixed:
        name = "fixed"

        def decide(self, obs, rng):
            return Decision(probs={Action.IDLE: 1.0}, action=Action.IDLE, t_wall_ns=1)

    assert isinstance(Fixed(), Arbiter)
    decision = Fixed().decide(Observation(0, 0, 0, 0), None)
    assert decision.t_sim_ms is None and decision.meta == {}
    assert not hasattr(decision, "t_server_ms")  # dropped by decision D10


def test_stopwatch_measures_known_delay():
    with Stopwatch() as sw:
        busy_wait_ns(10_000_000)
    assert 10_000_000 <= sw.elapsed_ns < 12_000_000


def test_busy_wait_is_precise():
    t0 = time.perf_counter_ns()
    busy_wait_ns(5_000_000)
    assert 5_000_000 <= time.perf_counter_ns() - t0 < 7_000_000


def test_summarize_ns_percentiles():
    summary = summarize_ns(ms * 1_000_000 for ms in range(1, 101))
    assert summary.n == 100
    assert summary.p50_ms == pytest.approx(50.5)
    assert summary.p95_ms == pytest.approx(95.05)
    assert summary.mean_ms == pytest.approx(50.5)


def test_summarize_ns_rejects_empty():
    with pytest.raises(ValueError):
        summarize_ns([])


def test_sysinfo_collects_without_raising():
    host = sysinfo.collect()
    assert host.default_workers >= 1
    assert host.machine
