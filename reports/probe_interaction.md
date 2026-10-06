# Pathway interaction after calibration (exploratory, decision D26)

Date: 2026-09-20. Exploratory, **not** G4/G7 gates. Encoding calibrated under D25 (`reports/calibration.md`): sugar `R_max` 102.8 Hz, looming 2.34 Hz; decoder: EAT — 4 MN9 spikes in 50 ms (θ = 74.8 Hz), ESCAPE — one spike from either DNp01, first event wins; `alpha` unset, hunger = 0. Connectome v783, `event` backend, full 500 ms trials. Nothing changed after viewing results.

Slice: sugar = 0.6 × looming 0…1 (11 levels) × 20 repetitions, seeds 7,100,000+. Script: `scripts/probe_interaction.py`; data: `runs/20260920T111444_probe-interaction/`; all trials (real graph and 20 shuffles): `reports/probe_interaction_trials.csv`.

## 1. Real graph: conflict slice

| looming | EAT / ESCAPE / IDLE decisions (out of 20) | MN9 rate, Hz: mean (SD) | MN9 crossed threshold | Crossing t_sim, ms: p50 [min–max] | DNp01 spiked | First DNp01 spike t_sim, ms | Active neurons |
|---|---|---|---|---|---|---|---|
| 0.0 | 18 / 0 / 2 | 26.9 (8.3) | 18/20 | 142 [77–498] | 0/20 | — | 254 |
| 0.1 | 18 / 0 / 2 | 28.2 (9.2) | 18/20 | 228 [67–488] | 0/20 | — | 288 |
| 0.2 | 18 / 1 / 1 | 29.6 (9.9) | 19/20 | 188 [88–429] | 1/20 | 322 [322–322] | 324 |
| 0.3 | 18 / 1 / 1 | 29.7 (8.0) | 19/20 | 133 [77–266] | 2/20 | 246 [43–449] | 365 |
| 0.4 | 18 / 2 / 0 | 29.1 (6.5) | 19/20 | 171 [60–407] | 3/20 | 70 [43–494] | 391 |
| 0.5 | 15 / 4 / 1 | 26.5 (9.1) | 18/20 | 154 [72–462] | 5/20 | 199 [69–459] | 407 |
| 0.6 | 17 / 3 / 0 | 28.2 (11.0) | 18/20 | 147 [82–456] | 6/20 | 213 [167–408] | 422 |
| 0.7 | 13 / 7 / 0 | 29.7 (9.9) | 18/20 | 136 [89–409] | 13/20 | 213 [36–428] | 451 |
| 0.8 | 10 / 10 / 0 | 27.5 (7.6) | 19/20 | 206 [97–449] | 13/20 | 134 [35–429] | 486 |
| 0.9 | 12 / 7 / 1 | 31.1 (7.7) | 17/20 | 123 [71–340] | 16/20 | 240 [31–430] | 506 |
| 1.0 | 13 / 7 / 0 | 28.7 (6.5) | 20/20 | 197 [64–400] | 17/20 | 230 [44–456] | 517 |

Exact ties (EAT and ESCAPE in the same 0.1 ms step): 0 of 220.

## 2. Looming suppression of MN9 (repeat of N2)

- MN9 rate at sugar = 0.6 by looming level 0 … 1: 26.9 / 28.2 / 29.6 / 29.7 / 29.1 / 26.5 / 28.2 / 29.7 / 27.5 / 31.1 / 28.7 Hz. At looming = 0: 26.9 Hz; at looming = 1: 28.7 Hz. Minimum across levels 26.5, maximum 31.1 Hz.
- In the overnight probe (`reports/probe_looming.md` §5, `R_max` = 200 Hz for both channels), the same quantity fell from 69.5 Hz to 0. LPLC2/LC4 input there was 20–200 Hz per neuron; here it is at most 2.34 Hz.
- MN9 crossed the EAT threshold in 17/20 to 20/20 trials, without a looming trend.

## 3. Reverse direction: DNp01 after adding sugar

Control: the same looming levels and **same trial seeds**, but sugar = 0 (`runs/20260920T111444_probe-interaction/looming_only.json`).

| looming | DNp01 spiked, looming-only | t_sim, ms | DNp01 spiked, sugar 0.6 + looming | t_sim, ms | Active neurons: looming-only | sugar + looming |
|---|---|---|---|---|---|---|
| 0.0 | 0/20 | — | 0/20 | — | 0 | 254 |
| 0.1 | 0/20 | — | 0/20 | — | 35 | 288 |
| 0.2 | 1/20 | 321 [321–321] | 1/20 | 322 [322–322] | 70 | 324 |
| 0.3 | 2/20 | 245 [43–447] | 2/20 | 246 [43–449] | 98 | 365 |
| 0.4 | 5/20 | 368 [43–493] | 3/20 | 70 [43–494] | 122 | 391 |
| 0.5 | 12/20 | 226 [69–455] | 5/20 | 199 [69–459] | 151 | 407 |
| 0.6 | 12/20 | 248 [85–407] | 6/20 | 213 [167–408] | 168 | 422 |
| 0.7 | 20/20 | 121 [36–480] | 13/20 | 213 [36–428] | 192 | 451 |
| 0.8 | 20/20 | 107 [35–329] | 13/20 | 134 [35–429] | 213 | 486 |
| 0.9 | 20/20 | 150 [31–406] | 16/20 | 240 [31–430] | 240 | 506 |
| 1.0 | 20/20 | 98 [44–371] | 17/20 | 230 [44–456] | 254 | 517 |

- At looming ≥ 0.5 (6 levels × 20 trials), DNp01 spiked in **104 of 120** trials without sugar and **70 of 120** at sugar 0.6. Two-sided Fisher exact test: p = 1.2e-06. The test was selected after viewing data; exploratory.
- Direct sugar-active connections to DNp01 (from the overnight probe, at a different `R_max`): 4 inhibitory edges, 7 synapses; onto DNp01 presynaptic partners: 599 inhibitory edges (3,859 synapses) and 188 excitatory edges (992). Active sets were not recomputed under calibrated input.

## 4. Comparison with an independent race

Prediction: pair each of 20 sugar-only trials (looming = 0) with each of 20 looming-only trials at that level (400 pairs); the earlier event wins. This simplifies the G7 null model (SPEC §5); it is not the gate itself.

| looming | Independent race: EAT / ESCAPE / IDLE | Observed conflict: EAT / ESCAPE / IDLE |
|---|---|---|
| 0.0 | 0.90 / 0.00 / 0.10 | 0.90 / 0.00 / 0.10 |
| 0.1 | 0.90 / 0.00 / 0.10 | 0.90 / 0.00 / 0.10 |
| 0.2 | 0.89 / 0.01 / 0.10 | 0.90 / 0.05 / 0.05 |
| 0.3 | 0.85 / 0.06 / 0.09 | 0.90 / 0.05 / 0.05 |
| 0.4 | 0.80 / 0.13 / 0.07 | 0.90 / 0.10 / 0.00 |
| 0.5 | 0.68 / 0.28 / 0.04 | 0.75 / 0.20 / 0.05 |
| 0.6 | 0.70 / 0.26 / 0.04 | 0.85 / 0.15 / 0.00 |
| 0.7 | 0.36 / 0.64 / 0.00 | 0.65 / 0.35 / 0.00 |
| 0.8 | 0.31 / 0.69 / 0.00 | 0.50 / 0.50 / 0.00 |
| 0.9 | 0.39 / 0.61 / 0.00 | 0.60 / 0.35 / 0.05 |
| 1.0 | 0.28 / 0.72 / 0.00 | 0.65 / 0.35 / 0.00 |

## 5. Twenty shuffled graphs

Degree- and sign-preserving shuffling (`lif/shuffle.py`, seeds 1–20): edge targets permuted separately within excitatory and inhibitory edges. Identical stimuli, trial seeds, encoding, and decoder parameters (shuffled graphs were **not** recalibrated). 220 trials per graph, 4,400 total.

| Graph | Trials with MN9 spikes | Maximum MN9 rate, Hz | Trials with DNp01 spikes | EAT / ESCAPE / IDLE decisions | Active neurons (mean) |
|---|---|---|---|---|---|
| shuffle_01 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 166 |
| shuffle_02 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 167 |
| shuffle_03 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 170 |
| shuffle_04 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 165 |
| shuffle_05 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 188 |
| shuffle_06 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 165 |
| shuffle_07 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 165 |
| shuffle_08 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 166 |
| shuffle_09 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 168 |
| shuffle_10 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 166 |
| shuffle_11 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 165 |
| shuffle_12 | 0/220 | 0.0 | 5/220 | 0 / 5 / 215 | 173 |
| shuffle_13 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 166 |
| shuffle_14 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 165 |
| shuffle_15 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 176 |
| shuffle_16 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 167 |
| shuffle_17 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 167 |
| shuffle_18 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 175 |
| shuffle_19 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 166 |
| shuffle_20 | 0/220 | 0.0 | 0/220 | 0 / 0 / 220 | 166 |

- MN9 emitted at least one spike in **0 of 4,400** trials; DNp01 in **5 of 4,400** (all in one graph).
- Mean active-neuron count: 401 on the real graph versus 169 on shuffled graphs (including the 20 sugar GRNs and up to 314 directly stimulated LPLC2/LC4).
- Neither circuit propagates activity to its readout neuron in shuffled graphs, so pathway interaction cannot be assessed there: no output activity is available to interact.

## 6. Not included

- Recomputed active-neuron sets and cross-pathway synapses under calibrated input (section 4 of the overnight probe used `R_max` = 200 Hz).
- Other sugar levels; bitter input; hunger; sugar slices at fixed looming.
- Formal G7 testing (prespecified statistics and repetition count) or G4 (G1–G3 metrics against a null distribution).
- Recalibration of shuffled graphs.
