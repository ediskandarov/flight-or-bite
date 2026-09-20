"""Sensory encoding: observation -> Poisson rates of the channel neuron sets."""

import numpy as np
import pytest

from flight_or_bite.lif.encoding import Encoding, load_encoding
from flight_or_bite.types import Observation

ENC = Encoding(t_sim_ms=500, r_max_sugar_hz=100, r_max_bitter_hz=100, r_max_looming_hz=2,
               theta_eat_hz=75, eat_window_ms=50)  # fmt: skip


def test_rates_scale_linearly_per_channel():
    assert ENC.rates(Observation(0.5, 0.2, 1.0, 0.9)) == {
        "sugar": 50.0,
        "bitter": 20.0,
        "looming": 2.0,
    }


def test_unset_alpha_means_hunger_is_ignored_and_a_set_alpha_is_a_gain_on_sugar_only():
    fed, starving = Observation(0.5, 0.2, 1.0, 0.0), Observation(0.5, 0.2, 1.0, 1.0)
    assert ENC.rates(fed) == ENC.rates(starving)
    hungry = ENC.model_copy(update={"alpha": 0.5}).rates(starving)
    assert hungry == {"sugar": 75.0, "bitter": 20.0, "looming": 2.0}


def test_stimulus_covers_only_the_supplied_channels():
    sets = {"sugar": np.array([3, 4]), "looming": np.array([7, 8, 9])}
    stim = ENC.stimulus(Observation(0.6, 0.9, 0.5, 0.0), sets)
    assert stim.neurons.tolist() == [3, 4, 7, 8, 9]
    assert stim.rates_hz.tolist() == pytest.approx([60.0, 60.0, 1.0, 1.0, 1.0])


def test_project_encoding_is_the_calibrated_one():
    enc = load_encoding()
    assert enc.r_max_bitter_hz == enc.r_max_sugar_hz  # decision D25
    assert enc.r_max_looming_hz < enc.r_max_sugar_hz and enc.eat_window_ms == 50.0
    assert enc.alpha == 1.0 and enc.calibration_run  # decision D32
