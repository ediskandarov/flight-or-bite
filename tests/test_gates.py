"""Gate statistics and the ablation switch of the kernel (the gates themselves run on real data)."""

import numpy as np
import pytest
import yaml

from flight_or_bite.eval.stats import holm, mcnemar_exact
from flight_or_bite.lif.backend import Stimulus
from flight_or_bite.lif.decoder import spikes_needed
from flight_or_bite.lif.event_backend import EventBackend
from flight_or_bite.lif.graph import from_edges
from flight_or_bite.lif.params import load_params
from flight_or_bite.validation.gates_m3 import EAT_WINDOW_S, load_cfg

PARAMS = load_params()


def test_mcnemar_counts_discordant_pairs_and_is_exact():
    control = [True] * 10 + [False] * 5
    condition = [False] * 6 + [True] * 4 + [True] * 1 + [False] * 4
    r = mcnemar_exact(control, condition)
    assert (r["b"], r["c"], r["control_yes"], r["condition_yes"], r["n"]) == (6, 1, 10, 5, 15)
    assert r["p"] == pytest.approx(2 * (1 + 7) / 2**7)  # two-sided binomial(7, 0.5): P(X <= 1) * 2
    assert mcnemar_exact([True, False], [True, False])["p"] == 1.0  # no discordant pairs
    with pytest.raises(ValueError):
        mcnemar_exact([True], [True, False])


def test_holm_adjustment():
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm([0.5, 0.5]) == pytest.approx([1.0, 1.0])
    assert holm([0.2]) == [0.2] and holm([]) == []


def test_ablated_neuron_cannot_fire_while_a_silenced_one_still_does():
    chain = from_edges(0, np.arange(3), np.array([0, 1]), np.array([1, 2]), np.array([400, 400]))
    backend = EventBackend(chain, PARAMS)
    stim = Stimulus.uniform(np.array([0]), 0.0)
    kicks = (np.array([10], dtype=np.int64), np.array([0], dtype=np.int32))
    intact = backend.run_trial(stim, 80.0, seed=0, kicks=kicks)
    silenced = backend.run_trial(stim, 80.0, seed=0, kicks=kicks, silenced=np.array([1]))
    ablated = backend.run_trial(stim, 80.0, seed=0, kicks=kicks, ablated=np.array([1]))
    assert [len(intact.times_of(n)) for n in (0, 1, 2)] == [1, 1, 1]
    assert [len(silenced.times_of(n)) for n in (0, 1, 2)] == [1, 1, 0]  # fires, affects nobody
    assert [len(ablated.times_of(n)) for n in (0, 1, 2)] == [1, 0, 0]  # never fires


def test_gate_protocol_is_complete_and_uses_the_specs_thresholds():
    cfg = load_cfg()
    assert set(cfg) == {"G1", "G2", "G3", "G4", "G5", "G6", "G7"}
    assert (cfg["G1"]["threshold"], cfg["G2"]["threshold"], cfg["G3"]["threshold"]) == (
        0.8,
        0.2,
        0.8,
    )
    assert len(cfg["G4"]["shuffle_seeds"]) == 20 and cfg["G4"]["percentile"] == 95
    assert cfg["G7"]["looming_levels"] == [0.6, 0.8, 1.0] and cfg["G7"]["n_rep"] == 40
    seeds = [cfg[g]["seed_base"] for g in ("G1", "G2", "G3", "G5", "G7")]
    assert len(set(seeds)) == 5  # gates never share trial seeds
    for k in (3, 5):  # the theta variants of G6 really mean k spikes in the 50 ms window
        assert spikes_needed((k - 0.5) / EAT_WINDOW_S, 50.0) == k


def test_frozen_encoding_matches_decision_d36():
    enc = yaml.safe_load(open("configs/encoding.yaml"))
    assert round(enc["r_max_sugar_hz"], 1) == 102.8 and round(enc["r_max_looming_hz"], 2) == 2.34
    assert spikes_needed(enc["theta_eat_hz"], enc["eat_window_ms"]) == 4 and enc["alpha"] == 1.0
