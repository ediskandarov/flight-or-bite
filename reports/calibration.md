# Channel calibration (decision D25)

Date: 2026-09-20. Protocol fixed in `configs/calibration.yaml` before the run; script `scripts/calibrate.py`; data `runs/20260920T104933_calibration/calibration.json`. Connectome v783, `event` backend, full 500 ms trials, decoding after each trial. No quantity depends on Jev, the oracle, or arbiter comparisons. `alpha` is unset (hunger does not affect encoding).

## 1. MN9 saturation and EAT threshold

20 sugar GRNs stimulated at the specified rate; MN9 rate over the full 500 ms window, mean of 20 trials (dev seeds 0–19).

| GRN input, Hz | MN9, Hz (mean) | SD |
|---|---|---|
| 50 | 10.7 | 5.1 |
| 100 | 60.7 | 7.9 |
| 200 | 86.8 | 6.4 |
| 400 | 109.5 | 6.6 |
| 800 | 128.2 | 5.1 |
| 1600 | 139.9 | 7.9 |
| 3200 | 149.6 | 4.1 |

- “Saturation” is operationally the highest mean in this series: **149.6 Hz**. There is no plateau: MN9 firing increased 6.9% between the final two points (input doubled). A broader series would give a higher value.
- **`theta_eat` = 74.8 Hz** (half). In a sliding 50 ms window this means **4 MN9 spikes within 50 ms**, effectively 80 Hz: spike counts are integers, so 74.8 Hz (3.74 spikes) rounds upward.

## 2. R_max bisection

Target: P(response) = 0.5 at stimulus 0.5, with other channels silent. 50 trials per step, dev seeds 0–49, identical at each step (common random numbers). Result: upper endpoint of the final bracket (lowest tested `R_max` with p ≥ 0.5).

**Sugar → EAT.** `R_max` = **102.783 Hz** (bracket 102.539–102.783).

| Step | R_max, Hz | Input at sugar 0.5, Hz | P(EAT) |
|---|---|---|---|
| 0 | 0.000 | 0.000 | 0.00 |
| 1 | 2000.000 | 1000.000 | 1.00 |
| 2 | 1000.000 | 500.000 | 1.00 |
| 3 | 500.000 | 250.000 | 1.00 |
| 4 | 250.000 | 125.000 | 1.00 |
| 5 | 125.000 | 62.500 | 0.90 |
| 6 | 62.500 | 31.250 | 0.00 |
| 7 | 93.750 | 46.875 | 0.30 |
| 8 | 109.375 | 54.688 | 0.78 |
| 9 | 101.562 | 50.781 | 0.40 |
| 10 | 105.469 | 52.734 | 0.62 |
| 11 | 103.516 | 51.758 | 0.66 |
| 12 | 102.539 | 51.270 | 0.46 |
| 13 | 103.027 | 51.514 | 0.54 |
| 14 | 102.783 | 51.392 | 0.50 |

**Looming → ESCAPE** (input to all 314 bilateral LPLC2+LC4; ESCAPE = one spike from either DNp01). `R_max` = **2.344 Hz** (bracket 2.148–2.344).

| Step | R_max, Hz | Input at looming 0.5, Hz | P(ESCAPE) |
|---|---|---|---|
| 0 | 0.000 | 0.000 | 0.00 |
| 1 | 100.000 | 50.000 | 1.00 |
| 2 | 50.000 | 25.000 | 1.00 |
| 3 | 25.000 | 12.500 | 1.00 |
| 4 | 12.500 | 6.250 | 1.00 |
| 5 | 6.250 | 3.125 | 1.00 |
| 6 | 3.125 | 1.562 | 0.86 |
| 7 | 1.562 | 0.781 | 0.14 |
| 8 | 2.344 | 1.172 | 0.50 |
| 9 | 1.953 | 0.977 | 0.28 |
| 10 | 2.148 | 1.074 | 0.42 |

- Looming `R_max` is 44 times smaller than sugar `R_max`. At looming = 0.5, each of the 314 input neurons emits an average of 0.59 spikes per 500 ms trial.
- P estimated from 50 trials is nonmonotonic between neighboring sugar-bisection steps (103.5 Hz → 0.66, 105.5 Hz → 0.62): probability resolution is 0.02, reflecting finite-sample noise.
- Bitter `R_max` equals sugar `R_max` (102.783 Hz) under D25; it was not calibrated or yet used in simulations. The bitter GRN set (65 from annotations or 20 from the authors' list) remains undecided.

## 3. Independent-seed check

50 trials per level, dev seeds 500–549 (not used in bisection). Single stimulus, full decoder.

**Sugar** (`R_max` = 102.8 Hz):

| sugar | Input, Hz | P(EAT) | EAT decision t_sim, ms: p50 [min–max] | EAT / ESCAPE / IDLE fractions |
|---|---|---|---|---|
| 0.0 | 0.00 | **0.00** | — | 0.00 / 0.00 / 1.00 |
| 0.1 | 10.28 | **0.00** | — | 0.00 / 0.00 / 1.00 |
| 0.2 | 20.56 | **0.00** | — | 0.00 / 0.00 / 1.00 |
| 0.3 | 30.83 | **0.00** | — | 0.00 / 0.00 / 1.00 |
| 0.4 | 41.11 | **0.10** | 392.0 [163.3–481.2] | 0.10 / 0.00 / 0.90 |
| 0.5 | 51.39 | **0.50** | 232.2 [84.1–482.0] | 0.50 / 0.00 / 0.50 |
| 0.6 | 61.67 | **0.98** | 146.7 [69.0–478.8] | 0.98 / 0.00 / 0.02 |
| 0.7 | 71.95 | **1.00** | 92.4 [53.9–302.6] | 1.00 / 0.00 / 0.00 |
| 0.8 | 82.23 | **1.00** | 79.8 [50.1–201.8] | 1.00 / 0.00 / 0.00 |
| 0.9 | 92.50 | **1.00** | 70.8 [53.7–165.7] | 1.00 / 0.00 / 0.00 |
| 1.0 | 102.78 | **1.00** | 61.1 [49.6–345.4] | 1.00 / 0.00 / 0.00 |

**Looming** (`R_max` = 2.34 Hz):

| looming | Input, Hz | P(ESCAPE) | ESCAPE decision t_sim, ms: p50 [min–max] | EAT / ESCAPE / IDLE fractions |
|---|---|---|---|---|
| 0.0 | 0.00 | **0.00** | — | 0.00 / 0.00 / 1.00 |
| 0.1 | 0.23 | **0.00** | — | 0.00 / 0.00 / 1.00 |
| 0.2 | 0.47 | **0.00** | — | 0.00 / 0.00 / 1.00 |
| 0.3 | 0.70 | **0.08** | 400.5 [156.8–495.4] | 0.00 / 0.08 / 0.92 |
| 0.4 | 0.94 | **0.26** | 377.3 [119.1–496.2] | 0.00 / 0.26 / 0.74 |
| 0.5 | 1.17 | **0.50** | 251.3 [50.4–487.5] | 0.00 / 0.50 / 0.50 |
| 0.6 | 1.41 | **0.84** | 272.3 [34.1–481.1] | 0.00 / 0.84 / 0.16 |
| 0.7 | 1.64 | **0.90** | 184.0 [32.7–456.7] | 0.00 / 0.90 / 0.10 |
| 0.8 | 1.88 | **1.00** | 116.8 [32.7–448.5] | 0.00 / 1.00 / 0.00 |
| 0.9 | 2.11 | **1.00** | 98.9 [32.3–407.4] | 0.00 / 1.00 / 0.00 |
| 1.0 | 2.34 | **1.00** | 87.4 [31.8–279.6] | 0.00 / 1.00 / 0.00 |
