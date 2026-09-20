"""Shuffled connectome: degrees and signs preserved, wiring destroyed, reproducible by seed."""

import numpy as np

from flight_or_bite.lif.graph import from_edges
from flight_or_bite.lif.shuffle import shuffled


def graph(n=300, e=6000, seed=2):
    rng = np.random.default_rng(seed)
    pre = rng.integers(0, n, e)
    post = (pre + rng.integers(1, n, e)) % n  # no self-loops in the original
    sign = np.where(rng.random(n) < 0.6, 1, -1)  # sign is a property of the presynaptic neuron
    return from_edges(1, np.arange(n), pre, post, sign[pre] * rng.integers(1, 50, e))


def in_degree(g, mask):
    return np.bincount(g.post[mask], minlength=g.n_neurons)


def test_degrees_signs_and_weights_are_preserved():
    g = graph()
    s = shuffled(g, seed=1)
    assert np.array_equal(np.diff(s.indptr), np.diff(g.indptr))  # out-degree
    assert np.array_equal(s.count, g.count)  # per-edge weights stay with their source, in order
    for sign in (1, -1):  # excitatory and inhibitory in-degree separately
        assert np.array_equal(in_degree(s, np.sign(s.count) == sign), in_degree(g, np.sign(g.count) == sign))
    assert np.array_equal(np.sort(s.post), np.sort(g.post))


def test_wiring_is_destroyed_without_self_loops():
    g = graph()
    s = shuffled(g, seed=1)
    assert np.mean(s.post != g.post) > 0.95
    assert not np.any(s.pre() == s.post)


def test_reproducible_by_seed_and_different_across_seeds():
    g = graph()
    assert np.array_equal(shuffled(g, 5).post, shuffled(g, 5).post)
    assert not np.array_equal(shuffled(g, 5).post, shuffled(g, 6).post)
    assert np.array_equal(g.post, graph().post)  # the original is not modified
