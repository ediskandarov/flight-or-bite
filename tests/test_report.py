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


def test_secondary_comparison_does_not_declare_a_primary_winner():
    from flight_or_bite.report.build import main_metric

    summary = {"episodes": 100, "stops": [], "retried_decisions": {"jev_informed": 0},
               "arbiters": {}, "paired_differences": {
                   "jev_informed - connectome": {"mean_diff": 5.91, "ci95": [0.63, 11.03], "significant": True}}}
    secondary = "\n".join(main_metric(summary, "Secondary", False))
    primary = "\n".join(main_metric(summary, "Primary", True))
    assert "вторичный анализ" in secondary and "победитель: `" not in secondary
    assert "победитель: `jev_informed`" in primary
    assert "решений с повтором после сетевой ошибки: 0." in secondary
