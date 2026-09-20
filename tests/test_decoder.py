"""Motor decoder: sliding-window MN9 rate, single DNp01 spike, first one wins."""

import numpy as np
import pytest

from flight_or_bite.lif.backend import TrialResult
from flight_or_bite.lif.decoder import decode, rate_crossing_ms, spikes_needed
from flight_or_bite.types import Action

MN9, DN = 7, np.array([3, 4])


def trial(mn9_times=(), dn_times=(), dn_neuron=3):
    i = [MN9] * len(mn9_times) + [dn_neuron] * len(dn_times)
    t = [*mn9_times, *dn_times]
    return TrialResult(np.array(i, dtype=np.int32), np.array(t, dtype=float), 500.0, False, 1)


def run(result, theta=45.0, window=50.0):
    return decode(result, MN9, DN, theta_eat_hz=theta, eat_window_ms=window, t_sim_ms=500.0)


@pytest.mark.parametrize(
    ("theta", "needed"), [(45.0, 3), (40.0, 2), (40.1, 3), (20.0, 1), (5.0, 1), (100.0, 5)]
)
def test_a_rate_threshold_is_a_whole_number_of_spikes_in_the_window(theta, needed):
    assert spikes_needed(theta, 50.0) == needed


def test_rate_crossing_is_the_spike_that_completes_the_count():
    assert rate_crossing_ms(np.array([10.0, 30.0, 55.0]), 45.0, 50.0) == 55.0  # 3 spikes in 45 ms
    assert (
        rate_crossing_ms(np.array([10.0, 30.0, 60.0]), 45.0, 50.0) is None
    )  # 50 ms apart: not < window
    assert rate_crossing_ms(np.array([10.0, 100.0, 120.0, 140.0]), 45.0, 50.0) == 140.0
    assert rate_crossing_ms(np.array([10.0, 20.0]), 45.0, 50.0) is None
    assert rate_crossing_ms(np.array([]), 45.0, 50.0) is None


def test_nothing_happens_is_idle_at_t_sim():
    d = run(trial())
    assert (d.action, d.t_sim_ms, d.t_eat_ms, d.t_escape_ms) == (Action.IDLE, 500.0, None, None)
    assert run(trial(mn9_times=[10.0, 200.0, 400.0])).action is Action.IDLE  # too sparse


def test_eat_when_mn9_crosses_first():
    d = run(trial(mn9_times=[10.0, 20.0, 30.0], dn_times=[80.0]))
    assert (d.action, d.t_sim_ms, d.t_escape_ms) == (Action.EAT, 30.0, 80.0)


def test_escape_on_a_single_dnp01_spike_of_either_side():
    for neuron in (3, 4):
        d = run(trial(mn9_times=[10.0, 20.0, 30.0], dn_times=[12.5], dn_neuron=neuron))
        assert (d.action, d.t_sim_ms, d.t_eat_ms) == (Action.ESCAPE, 12.5, 30.0)
    assert run(trial(dn_times=[499.9])).action is Action.ESCAPE


def test_exact_tie_goes_to_escape_and_is_flagged():
    d = run(trial(mn9_times=[10.0, 20.0, 30.0], dn_times=[30.0]))
    assert d.action is Action.ESCAPE and d.tie
    assert not run(trial(mn9_times=[10.0, 20.0, 30.0], dn_times=[30.1])).tie


FROZEN_THETA = 74.8  # 4 spikes within 50 ms (decision D36)


def test_decisions_do_not_depend_on_the_float_representation_of_a_step():
    """39.2 and 39.199999999999996 are the same 0.1 ms step (seen in the Brian2 cross-check)."""
    a = run(trial(mn9_times=[10.0, 20.0, 39.2, 59.9]), theta=FROZEN_THETA)
    b = run(
        trial(mn9_times=[10.0, 20.0, 39.199999999999996, 59.900000000000006]), theta=FROZEN_THETA
    )
    assert (a.action, a.t_sim_ms) == (b.action, b.t_sim_ms) == (Action.EAT, 59.9)


def test_a_burst_spanning_exactly_the_window_does_not_count_whatever_the_rounding():
    for start in (0.3, 17.1, 123.7):  # start + 50.0 is rarely exact in floating point
        spikes = [start, start + 10.0, start + 20.0, start + 50.0]
        assert run(trial(mn9_times=spikes), theta=FROZEN_THETA).action is Action.IDLE
        assert (
            run(trial(mn9_times=[start, start + 10.0, start + 20.0, start + 49.9])).action
            is Action.EAT
        )
