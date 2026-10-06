# Validity gates (M3)

Protocol: `configs/gates.yaml`, fixed in commit `921ffaf` **before** the run; only crash testing on unrelated seeds preceded it (outputs were not inspected). Run: `runs/20260920T135908_gates`. Connectome v783, `event` backend, frozen rate encoding (D36), D25 decoder, full 500 ms trials. Nothing was changed after viewing results. Raw results: `reports/gates/G*.json`.

| # | Gate | Metric | Threshold | Status |
|---|---|---|---|---|
| G1 | Sugar → MN9 | 0.9509 | 0.8 | **passed** |
| G2 | Bitter suppresses sugar | 1 | 0.2 | **passed** |
| G3 | Looming → DNp01 | 0.9954 | 0.8 | **passed** |
| G4 | Real versus shuffled | 3 | 3 | **passed** |
| G5 | Ablation | 3 | 3 | **passed** |
| G6 | Robustness | 9 | 11 | **FAILED** |
| G7 | Conflict versus independent race | 0.001465 | 0.05 | **passed** |

## G1. Sugar → MN9

Spearman ρ across all 110 trials: **0.951** (over level means: 0.991).

| sugar | 0 | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 | 1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MN9, Hz | 0 | 0 | 0 | 0.2 | 5.4 | 14.2 | 34.2 | 39.4 | 51.8 | 56.4 | 60.6 |

## G2. Bitter suppresses sugar

sugar = 0.6, 40 paired trials per level. Reduction in `p_eat` from bitter 0 to bitter 1: **100%**.

| bitter | 0 | 0.25 | 0.5 | 0.75 | 1 |
|---|---|---|---|---|---|
| p_eat | 0.97 | 0.80 | 0.20 | 0.03 | 0.00 |
| MN9, Hz | 30.5 | 17.5 | 4.8 | 0.8 | 0.1 |

## G3. Looming → DNp01

Spearman ρ between looming and `p_escape` across 11 levels (40 trials per level): **0.995**.

| looming | 0 | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 | 1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p_escape | 0.00 | 0.00 | 0.03 | 0.05 | 0.28 | 0.42 | 0.65 | 0.80 | 0.93 | 1.00 | 1.00 |
| t_sim ESCAPE p50, ms | — | — | 239 | 439 | 360 | 187 | 255 | 203 | 153 | 119 | 122 |

## G4. Real versus shuffled

20 degree- and sign-preserving shuffles (seeds 1–20), identical protocol, trial seeds, and encoding (no recalibration). **Signals do not reach the output neurons in shuffled graphs:** MN9 and DNp01 do not respond, so all three metrics equal 0 on each of the 20 graphs (an undefined metric for a constant response is treated as 0).

| Metric | Real graph | Null 95th percentile | Null maximum | Null values > 0 | Outside null distribution |
|---|---|---|---|---|---|
| G1 | 0.951 | 0.000 | 0.000 | 0 of 20 | yes |
| G2 | 1.000 | 0.000 | 0.000 | 0 of 20 | yes |
| G3 | 0.995 | 0.000 | 0.000 | 0 of 20 | yes |

## G5. Ablation

An ablated neuron cannot spike.

- Both DNp01 neurons ablated, looming = 1.0: `p_escape` = **0.00** (intact 1.00; criterion ≤ 0.05) — met.
- MN9 ablated, sugar = 1.0: `p_eat` = **0.00** (intact 1.00; criterion ≤ 0.05) — met.
- M_loom (25 neurons): retained effect fraction **0.00** (criterion ≤ 0.2) — met.
- cL20 alone: retained effect fraction **1.00** (no criterion). **Ablating cL20 does not remove the effect.** Its targets on this path are LC4 (343 synapses) and LPLC2 (2), out of 361 synapses onto looming-active DNp01 partners; these are clamped sources in the model (each Poisson input forces a spike regardless of inhibition), so this pathway is invisible by construction. Separate verification (`runs/cl20_check.json`): 17,916 LPLC2/LC4 spikes in 60 paired trials, zero differing sugar/no-sugar pairs. The model mechanism is carried by the other 24 M_loom neurons: ablating them while retaining cL20 removes the effect (b − c: 34 → 0, identical seeds).

Effect = b − c pooled over three looming levels (outcome: DNp01 spiked, looming-only versus sugar 0.6 + looming, identical seeds; ablation in both arms). Format: control → condition.

| Condition | looming 0.6 | looming 0.8 | looming 1.0 | Pooled | b − c |
|---|---|---|---|---|---|
| intact | 28/40 → 13/40; b = 15, c = 0; p = 6.1e-05 | 38/40 → 22/40; b = 16, c = 0; p = 3.1e-05 | 40/40 → 37/40; b = 3, c = 0; p = 0.25 | 106/120 → 72/120; b = 34, c = 0; p = 1.2e-10 | 34 |
| M_loom ablated | 28/40 → 27/40; b = 1, c = 0; p = 1 | 38/40 → 39/40; b = 0, c = 1; p = 1 | 40/40 → 40/40; b = 0, c = 0; p = 1 | 106/120 → 106/120; b = 1, c = 1; p = 1 | 0 |
| cL20 ablated | 28/40 → 13/40; b = 15, c = 0; p = 6.1e-05 | 38/40 → 22/40; b = 16, c = 0; p = 3.1e-05 | 40/40 → 37/40; b = 3, c = 0; p = 0.25 | 106/120 → 72/120; b = 34, c = 0; p = 1.2e-10 | 34 |

## G6. Robustness

**Failed.** Under SPEC §5 the final report must explicitly state: **“conclusions depend on manually chosen parameters.”** Both failed variants are ×0.5 weakening (`r_max_sugar × 0.5` and `w_syn × 0.5`); the network is silent (signals do not reach readout neurons), with no sign reversal.

A variant passes if affected gates retain direction and monotonicity: G1 ρ > 0.8, G3 ρ > 0.8, G2 reduction > 0. Passed: **9 of 11**. Fewer repetitions than in the main gates (G1 10, G2 20, G3 20); seeds offset by 100,000.

| Variant | G1: ρ | G2: p_eat reduction (p_eat at bitter 0 → 1) | G3: ρ | Passes |
|---|---|---|---|---|
| `r_max_sugar_x0.5` | 0.744 | 0.00 (0.00 → 0.00) | — | **no** |
| `r_max_sugar_x1.5` | 0.963 | 1.00 (1.00 → 0.00) | — | yes |
| `r_max_looming_x0.5` | — | — | 0.848 | yes |
| `r_max_looming_x1.5` | — | — | 0.915 | yes |
| `w_syn_x0.5` | 0 | 0.00 (0.00 → 0.00) | 0 | **no** |
| `w_syn_x1.5` | 0.937 | 0.95 (1.00 → 0.05) | 0.966 | yes |
| `alpha_0.5` | 0.963 | 1.00 (1.00 → 0.00) | — | yes |
| `alpha_1.5` | 0.965 | 0.95 (1.00 → 0.05) | — | yes |
| `theta_3_spikes` | — | 1.00 (1.00 → 0.00) | — | yes |
| `theta_5_spikes` | — | 1.00 (0.65 → 0.00) | — | yes |
| `looming_population_code` | — | — | 0.961 | yes |

Details for `r_max_sugar_x0.5`:
- MN9, Hz by sugar level: 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0.4 / 2 / 10.8 / 11.8

Details for `w_syn_x0.5`:
- MN9, Hz by sugar level: 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0 / 0
- p_escape by looming level: 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00 / 0.00

## G7. Conflict versus independent race (RQ1)

Null model: circuits are independent, so sugar input cannot change whether DNp01 spikes. sugar = 0.6, looming-only control on identical seeds, 40 pairs per level, exact two-sided McNemar test, Holm correction across three levels.

| looming | DNp01 spiked: control → condition; b, c; p | Control decisions EAT / ESCAPE / IDLE | Condition decisions |
|---|---|---|---|
| 0.6 | 29/40 → 15/40; b = 15, c = 1; p = 0.00052, p(Holm) = 0.0015 | 0 / 29 / 11 | 29 / 8 / 3 |
| 0.8 | 39/40 → 27/40; b = 12, c = 0; p = 0.00049, p(Holm) = 0.0015 | 0 / 39 / 1 | 26 / 14 / 0 |
| 1.0 | 40/40 → 34/40; b = 6, c = 0; p = 0.031, p(Holm) = 0.031 | 0 / 40 / 0 | 18 / 22 / 0 |
| pooled | 108/120 → 76/120; b = 33, c = 1; p = 4.1e-09 | | |

Minimum Holm-adjusted p: **0.0015** (threshold 0.05).

## Consequences under SPEC §5

- Failure of G1–G3 or G5 → stop and ask the human author. Failure of G4 → publish the negative result. Failure of G6 → state “conclusions depend on manually chosen parameters.” Failure of G7 → label “connectome = race of reflexes.”
- Not done in M3: G1 on Brian2 with frozen encoding (reference checked in M1 at `R_max` = 200 Hz: `reports/gates/G1_m1_r200.json`); recalibration on shuffled graphs.
