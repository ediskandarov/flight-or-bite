"""Early stopping at the decoder's event must not change the decision (synthetic graph)."""

import numpy as np
import pytest

from flight_or_bite.lif.backend import Stimulus, StopOnFirstSpike
from flight_or_bite.lif.decoder import decode, spikes_needed
from flight_or_bite.lif.event_backend import EventBackend
from flight_or_bite.lif.graph import from_edges
from flight_or_bite.lif.params import load_params

PARAMS = load_params()
THETA, WINDOW = 74.8, 50.0


def graph(seed=3, n=200, e=5000):
    rng = np.random.default_rng(seed)
    # neuron n is isolated: as the "escape" neuron it never fires, so the burst criterion decides
    return from_edges(0, np.arange(n + 1), rng.integers(0, n, e), rng.integers(0, n, e),
                      rng.integers(-100, 300, e))  # fmt: skip


def test_early_stop_gives_the_same_decision_and_time_as_the_full_trial():
    backend = EventBackend(graph(), PARAMS)
    stim = Stimulus.uniform(np.arange(8), 120.0)
    k, window_steps = spikes_needed(THETA, WINDOW), round(WINDOW / PARAMS.dt_ms)
    seen = set()
    cases = [(50, [60, 61]), (70, [71]), (120, [199]), (50, [200]), (70, [200]), (150, [200])]
    for burst_neuron, escape in cases:
        for seed in range(6):
            full = backend.run_trial(stim, 300.0, seed=seed)
            early = backend.run_trial(
                stim, 300.0, seed=seed, stop=StopOnFirstSpike(np.array(escape)),
                stop_on_burst=(burst_neuron, k, window_steps),
            )  # fmt: skip
            kw = dict(theta_eat_hz=THETA, eat_window_ms=WINDOW, t_sim_ms=300.0)
            a = decode(full, burst_neuron, np.array(escape), **kw)
            b = decode(early, burst_neuron, np.array(escape), **kw)
            assert (a.action, a.t_sim_ms) == (b.action, b.t_sim_ms)
            if a.action.value != "IDLE":
                assert early.stopped_early
                assert early.t_sim_ms == pytest.approx(a.t_sim_ms + PARAMS.dt_ms)  # stops right after
                assert early.spike_i.size <= full.spike_i.size
            seen.add(a.action.value)
    assert {"EAT", "ESCAPE"} <= seen  # both kinds of event were exercised


def test_no_burst_stop_without_the_option():
    backend = EventBackend(graph(), PARAMS)
    r = backend.run_trial(Stimulus.uniform(np.arange(8), 120.0), 100.0, seed=0)
    assert not r.stopped_early and r.t_sim_ms == 100.0
