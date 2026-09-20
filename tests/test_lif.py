"""LIF backends on synthetic graphs: semantics, early stopping, agreement with Brian2."""

import numpy as np
import pytest

from flight_or_bite.lif.backend import Stimulus, StopOnFirstSpike
from flight_or_bite.lif.circuits import CircuitSet, load_circuits, resolve
from flight_or_bite.lif.event_backend import EventBackend, poisson_schedule, replay_schedule
from flight_or_bite.lif.graph import from_edges
from flight_or_bite.lif.params import LIFParams, load_params
from flight_or_bite.lif.perf import spike_pairs

PARAMS = load_params()


def chain(count: int = 400):
    """0 -> 1 -> 2; 400 synapses = 110 mV of g per spike, enough to fire the target."""
    return from_edges(0, np.arange(3), np.array([0, 1]), np.array([1, 2]), np.array([count] * 2))


def random_graph(n=200, e=4000, seed=1):
    rng = np.random.default_rng(seed)
    return from_edges(0, np.arange(n), rng.integers(0, n, e), rng.integers(0, n, e), rng.integers(-150, 300, e))


def kick_at(steps, neuron=0):
    return np.asarray(steps, dtype=np.int64), np.full(len(steps), neuron, dtype=np.int32)


def test_params_match_the_reference_source():
    assert isinstance(PARAMS, LIFParams)
    assert (PARAMS.v_0_mv, PARAMS.v_rst_mv, PARAMS.v_th_mv) == (-52.0, -52.0, -45.0)
    assert (PARAMS.t_mbr_ms, PARAMS.tau_ms, PARAMS.t_rfc_ms, PARAMS.t_dly_ms) == (20, 5, 2.2, 1.8)
    assert (PARAMS.w_syn_mv, PARAMS.f_poi, PARAMS.dt_ms) == (0.275, 250.0, 0.1)
    assert (PARAMS.delay_steps, PARAMS.refractory_steps) == (18, 22)
    assert PARAMS.poisson_kick_mv == pytest.approx(68.75)


def test_graph_is_csr_by_presynaptic_neuron():
    g = from_edges(7, np.array([10, 20, 30]), np.array([2, 0, 2]), np.array([0, 1, 1]), np.array([5, -3, 9]))
    assert g.indptr.tolist() == [0, 1, 1, 3]
    assert g.post.tolist() == [1, 0, 1] and g.count.tolist() == [-3, 5, 9]
    assert g.pre().tolist() == [0, 2, 2]
    assert g.index_of([30, 10]).tolist() == [2, 0]
    with pytest.raises(KeyError, match="99"):
        g.index_of([10, 99])
    with pytest.raises(ValueError):
        from_edges(7, np.array([1]), np.array([0]), np.array([5]), np.array([1]))


def test_kick_fires_next_step_and_spike_travels_with_the_synaptic_delay():
    r = EventBackend(chain(), PARAMS).run_trial(Stimulus.uniform(np.array([0]), 0.0), 30.0, seed=0, kicks=kick_at([10]))
    steps = dict(
        zip(
            r.spike_i.tolist(),
            np.rint(r.spike_t_ms / PARAMS.dt_ms).astype(int).tolist(),
            strict=True,
        )
    )
    assert steps[0] == 11  # kick lands in step 10, threshold is crossed in step 11
    # delivered at 11 + 18 = 29; g = 110 mV then needs several steps to lift v by 7 mV
    assert 29 < steps[1] < 29 + 40
    assert not r.stopped_early and r.t_sim_ms == 30.0


def test_input_during_refractory_period_is_dropped():
    """Second presynaptic spike arrives 1 ms after the target fired: Brian2 discards it."""
    backend = EventBackend(chain(), PARAMS)
    stim = Stimulus.uniform(np.array([0]), 0.0)
    one = backend.run_trial(stim, 60.0, seed=0, kicks=kick_at([10]))
    t1 = int(np.rint(one.times_of(1)[0] / PARAMS.dt_ms))
    arrival_in_refractory = t1 + 10 - PARAMS.delay_steps - 1  # kick step so delivery = t1 + 10
    two = backend.run_trial(stim, 60.0, seed=0, kicks=kick_at([10, arrival_in_refractory]))
    assert len(two.times_of(1)) == 1
    late = backend.run_trial(stim, 60.0, seed=0, kicks=kick_at([10, arrival_in_refractory + 30]))
    assert len(late.times_of(1)) == 2  # the same input after the refractory period does fire it


def test_early_stop_halts_at_the_first_watched_spike():
    backend = EventBackend(chain(), PARAMS)
    stim = Stimulus.uniform(np.array([0]), 0.0)
    full = backend.run_trial(stim, 100.0, seed=0, kicks=kick_at([10, 300]))
    stopped = backend.run_trial(stim, 100.0, seed=0, kicks=kick_at([10, 300]), stop=StopOnFirstSpike(np.array([2])))
    first = full.times_of(2)[0]
    assert stopped.stopped_early
    assert stopped.t_sim_ms == pytest.approx(first + PARAMS.dt_ms)
    assert stopped.times_of(2).tolist() == [first]
    assert stopped.spike_i.size < full.spike_i.size
    idle = backend.run_trial(stim, 20.0, seed=0, kicks=kick_at([]), stop=StopOnFirstSpike(np.array([2])))
    assert not idle.stopped_early and idle.t_sim_ms == 20.0 and idle.spike_i.size == 0


def test_silencing_removes_outgoing_effect():
    backend = EventBackend(chain(), PARAMS)
    stim = Stimulus.uniform(np.array([0]), 0.0)
    r = backend.run_trial(stim, 80.0, seed=0, kicks=kick_at([10]), silenced=np.array([1]))
    assert len(r.times_of(1)) == 1 and len(r.times_of(2)) == 0


def test_trials_are_deterministic_by_seed_and_independent():
    backend = EventBackend(random_graph(), PARAMS)
    stim = Stimulus.uniform(np.arange(10), 200.0)
    a = backend.run_trial(stim, 100.0, seed=5)
    backend.run_trial(stim, 100.0, seed=6)  # state must not leak into the next trial
    b = backend.run_trial(stim, 100.0, seed=5)
    assert spike_pairs(a, PARAMS.dt_ms) == spike_pairs(b, PARAMS.dt_ms)
    assert spike_pairs(a, PARAMS.dt_ms) != spike_pairs(backend.run_trial(stim, 100.0, seed=6), 0.1)


def test_poisson_schedule_rate():
    stim = Stimulus.uniform(np.arange(50), 100.0)
    steps, neurons = poisson_schedule(stim, 10_000, 0.1, np.random.default_rng(0))  # 1 s
    assert len(steps) / 50 == pytest.approx(100.0, rel=0.05)
    assert set(neurons.tolist()) <= set(range(50))
    with pytest.raises(ValueError):
        poisson_schedule(Stimulus.uniform(np.array([0]), 20_000.0), 10, 0.1, np.random.default_rng(0))


def test_circuits_resolve_only_declared_absences():
    g = from_edges(783, np.array([10, 20]), np.array([0]), np.array([1]), np.array([1]))
    ok = CircuitSet(description="d", provenance="p", verified={783: "x"}, absent_in={783: [30]},
                    ids=[10, 30, 20])  # fmt: skip
    assert resolve(g, ok).tolist() == [0, 1]
    undeclared = ok.model_copy(update={"absent_in": {}})
    with pytest.raises(KeyError, match="30"):
        resolve(g, undeclared)
    with pytest.raises(KeyError, match="not verified"):
        resolve(from_edges(1, np.array([10]), np.array([0]), np.array([0]), np.array([1])), ok)


def test_project_circuits_file_is_well_formed():
    circuits = load_circuits()
    assert len(circuits["sugar_grn_right"].ids) == 21
    assert circuits["mn9"].ids == [720575940660219265]
    assert all(c.provenance.strip() for c in circuits.values())


def test_torch_cpu_backend_matches_event_backend():
    from flight_or_bite.lif.torch_backend import TorchBackend

    graph, stim = random_graph(), Stimulus.uniform(np.arange(10), 200.0)
    a = EventBackend(graph, PARAMS).run_trial(stim, 100.0, seed=5)
    b = TorchBackend(graph, PARAMS, device="cpu").run_trial(stim, 100.0, seed=5)
    assert spike_pairs(a, PARAMS.dt_ms) == spike_pairs(b, PARAMS.dt_ms)
    assert a.spike_i.size > 1000


@pytest.mark.brian2
def test_event_backend_is_spike_identical_to_brian2_on_replayed_input():
    from flight_or_bite.lif.brian2_backend import Brian2Backend

    graph, stim = random_graph(), Stimulus.uniform(np.arange(10), 200.0)
    reference = Brian2Backend(graph, PARAMS)
    candidate = EventBackend(graph, PARAMS)
    for seed in (1, 2):
        ref = reference.run_trial(stim, 150.0, seed=seed)
        kicks = replay_schedule(ref.spike_i, ref.spike_t_ms, stim.neurons, PARAMS.dt_ms)
        got = candidate.run_trial(stim, 150.0, seed=seed, kicks=kicks)
        assert ref.spike_i.size > 1000  # the comparison is not vacuous
        assert spike_pairs(ref, PARAMS.dt_ms) == spike_pairs(got, PARAMS.dt_ms)

    stop = StopOnFirstSpike(np.array([150]))
    early = reference.run_trial(stim, 150.0, seed=1, stop=stop)
    assert early.stopped_early and early.t_sim_ms < 150.0
