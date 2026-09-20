"""Report arithmetic (PREREG §7): Jensen-Shannon divergence and the psychometric fit."""

import numpy as np

from flight_or_bite.report.analyses import js, logistic_fit


def test_js_is_zero_for_equal_policies_and_one_bit_for_disjoint_ones():
    p, q = np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
    assert js(p, p) == 0.0 and np.isclose(js(p, q), 1.0) and np.isclose(js(p, q), js(q, p))


def test_logistic_fit_recovers_threshold_and_slope():
    x = np.linspace(0, 1, 7)
    fit = logistic_fit(x, 1 / (1 + np.exp(-12 * (x - 0.4))))
    assert np.isclose(fit["threshold"], 0.4, atol=1e-3) and np.isclose(fit["slope"], 12, atol=0.05)
    falling = logistic_fit(x, 1 / (1 + np.exp(9 * (x - 0.6))))
    assert np.isclose(falling["threshold"], 0.6, atol=1e-3) and falling["slope"] < 0


def test_a_step_policy_reports_the_midpoint_between_nodes():
    fit = logistic_fit(np.array([0.0, 0.25, 0.5, 0.75]), np.array([0.0, 0.0, 1.0, 1.0]))
    assert fit == {"threshold": 0.375, "slope": None, "degenerate": True}
