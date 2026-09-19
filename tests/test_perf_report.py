"""perf.md rendering: the recommendation must follow from the numbers and the verification."""

from flight_or_bite.lif.perf_report import render


def backend(name, rtf, wall):
    return {
        "backend": name, "t_load_s": 1.0, "n_full": 10, "full_wall_s_p50": wall,
        "full_wall_s_max": wall * 1.1, "rtf_p50": rtf, "spikes_per_trial": 6000.0,
        "mn9_rate_hz": 80.0, "n_stop": 10, "stop_fraction": 1.0, "stop_t_sim_ms_p50": 40.0,
        "stop_wall_s_p50": wall / 10, "first_trial_wall_s": wall * 5,
    }  # fmt: skip


def payload(throttled=False, verification=None, failures=None):
    return {
        "generated": "2026-09-19T22:00:00+03:00",
        "host": {"chip": "Apple M3 Pro", "performance_cores": 6, "efficiency_cores": 6,
                 "memory_gb": 36.0, "os_version": "Darwin 24.6.0", "python": "3.12.0"},
        "throttle": {"sleep_10ms_overshoot_ms_median": 95.0 if throttled else 1.2,
                     "sleep_10ms_overshoot_ms_max": 99.0, "timer_throttled": throttled,
                     "power": "Now drawing from 'AC Power'"},
        "connectome": {"version": 783, "neurons": 138639, "edges": 15091983, "t_graph_load_s": 0.4},
        "protocol": {"t_ms": 500.0, "rate_hz": 150.0, "n_stimulated": 20, "n_full": 10,
                     "n_stop": 10, "stop_rule": "first MN9 spike"},
        "backends": [backend("brian2", 0.4, 1.2), backend("event", 2.0, 0.25),
                     backend("torch-mps", 9.0, 0.05)],
        "failures": failures or {},
        "verification": verification if verification is not None else [
            {"backend": "event", "reference": "brian2-cython", "identical": 100, "union": 100},
            {"backend": "torch-mps", "reference": "brian2-cython", "identical": 90, "union": 110},
        ],
        "run_dir": "runs/x",
    }  # fmt: skip


def test_fastest_backend_is_not_recommended_unless_verified():
    text = render(payload())
    assert "**Backend: `event`**" in text  # torch-mps is faster here but differs from Brian2
    assert "| `event` | 100 | 100 | **bit-identical** |" in text
    assert "| `torch-mps` | 90 | 110 | differs |" in text
    assert "5.0x the Brian2 reference" in text


def test_reference_is_recommended_when_nothing_else_is_verified():
    assert "**Backend: `brian2`**" in render(payload(verification=[]))


def test_throttling_banner_and_failures_are_reported():
    text = render(payload(throttled=True, failures={"torch-mps": "RuntimeError: no MPS"}))
    assert "THROTTLED process" in text and "re-run `uv run fob perf`" in text
    assert "failed: RuntimeError: no MPS" in text
    assert "THROTTLED" not in render(payload())


def test_grid_cost_table_uses_the_measured_wall_time():
    text = render(payload())
    # 4500 sims * 0.25 s = 18.75 min on one process for the event backend
    assert "| `event` | 19 min |" in text
    assert "B. finer stimulus axes" in text and "1,225" in text
