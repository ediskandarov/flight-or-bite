# `event` versus Brian2 cross-check on conflict trials (decision D43)

Date: 2026-09-20. Script `scripts/crosscheck_conflict.py`; data `runs/20260920T154359_crosscheck-conflict/crosscheck.json`.

**Condition:** sugar = 0.6 + looming = 0.8, bitter = 0, hunger = 0; frozen rate encoding (20 sugar GRNs at 61.67 Hz, 314 LPLC2 + LC4 at 1.875 Hz); connectome v783; full 500 ms trials, dt 0.1 ms; seeds 0–9.

**Identical input.** Reference: Brian2 (Cython code generation), with equations, threshold, reset, and parameters copied verbatim from `model.py`; it generates input itself: one `PoissonInput` per stimulated neuron (334 total), as in `model.py`. Stimulated-neuron spikes from each Brian2 trial are replayed in `event` (each spike corresponds to an input on the previous step), giving the rest of the network bitwise-identical input in both simulators. Compare **every spike in the entire network** as (neuron, 0.1 ms step) pairs and apply the decoder to both outputs.

## Result

**26,502 of 26,502 spikes matched; zero differing pairs.** Decoder decisions and times matched **exactly** (the same number) in all 10 trials; the run was repeated after switching the decoder to integer steps.

| Seed | Input spikes | Brian2 spikes | event spikes | Matched | Brian2 only | event only | Active neurons | MN9 spikes | DNp01 spikes | Brian2 decision @ t_sim, ms | event decision @ t_sim, ms | Brian2 wall, s | event wall, s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 964 | 2,829 | 2,829 | 2,829 | 0 | 0 | 526 | 17 | 1 | ESCAPE @ 39.2 | ESCAPE @ 39.2 | 5.5 | 0.36 |
| 1 | 885 | 2,708 | 2,708 | 2,708 | 0 | 0 | 502 | 18 | 1 | ESCAPE @ 102.4 | ESCAPE @ 102.4 | 3.8 | 0.33 |
| 2 | 880 | 2,100 | 2,100 | 2,100 | 0 | 0 | 450 | 8 | 0 | EAT @ 230.7 | EAT @ 230.7 | 3.8 | 0.23 |
| 3 | 981 | 3,201 | 3,201 | 3,201 | 0 | 0 | 472 | 21 | 0 | EAT @ 192.3 | EAT @ 192.3 | 3.8 | 0.19 |
| 4 | 883 | 2,298 | 2,298 | 2,298 | 0 | 0 | 441 | 10 | 0 | EAT @ 336.1 | EAT @ 336.1 | 3.8 | 0.26 |
| 5 | 909 | 2,708 | 2,708 | 2,708 | 0 | 0 | 484 | 16 | 2 | ESCAPE @ 50.1 | ESCAPE @ 50.1 | 3.9 | 0.31 |
| 6 | 892 | 2,249 | 2,249 | 2,249 | 0 | 0 | 465 | 13 | 1 | EAT @ 157.3 | EAT @ 157.3 | 3.9 | 0.24 |
| 7 | 927 | 2,796 | 2,796 | 2,796 | 0 | 0 | 509 | 17 | 0 | EAT @ 195.0 | EAT @ 195.0 | 3.9 | 0.31 |
| 8 | 937 | 3,199 | 3,199 | 3,199 | 0 | 0 | 498 | 26 | 0 | EAT @ 95.5 | EAT @ 95.5 | 3.8 | 0.40 |
| 9 | 895 | 2,414 | 2,414 | 2,414 | 0 | 0 | 495 | 16 | 2 | EAT @ 136.8 | EAT @ 136.8 | 3.9 | 0.20 |

In the first run (`runs/20260920T152427_crosscheck-conflict`), serialized decision times differed: Brian2 represented the same 0.1 ms step as `39.199999999999996`, while `event` returned `39.2`. The decoder compared intervals in floating-point milliseconds, allowing a burst exactly one window long (500 steps) to count or not depending on rounding. The decoder now uses integer steps (`lif/decoder.py`, tests in `tests/test_decoder.py`). “DNp01 spiked” outcomes (G5, G7, H1–H3) are unaffected; `p_eat` and EAT `t_sim` could change only for bursts exactly 50.0 ms long. M3 gates predate the fix and were not rerun.

## What this does and does not verify

- Verifies network dynamics in the `event` kernel under **simultaneous** sugar and looming input: within-step operation order, 1.8 ms delay, refractoriness, input rejection by refractory neurons, reset, active set, summation order in `g`, and decoder.
- Earlier checks used the same method: sugar input on v630 (13,698 / 13,698 and 13,233 / 13,233 spikes), sugar input on v783 in `fob perf` (12,804 / 12,804), and a random mixed-sign graph (`tests/test_lif.py`, run in every test suite).
- Does not verify the `event` input generator (separate RNG streams per channel) against Brian2's generator: statistically equivalent (Bernoulli(rate · dt) per step), not bitwise identical. Nor does it verify ablation (`ablated`, without a counterpart in Brian2 `model.py`) or population looming encoding.
- Brian2 time per trial includes overhead from 334 `PoissonInput` objects; this is not a performance benchmark.
