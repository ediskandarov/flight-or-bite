# Loss from tabulating a known policy (exploratory)

Date: 2026-09-20. Question: how much survival is lost **solely to the grid and interpolation** when an exactly known policy is first tabulated (SPEC §4.5) and then played from that table (table mode, SPEC §2)? Oracle and `fixed_priority` are not the research subjects, so choosing a grid using them does not violate the no-tuning rule.

Method: evaluate the policy at grid nodes (1 repetition; both policies are deterministic), then use `TabularArbiter` for 1,000 `dev` episodes: linearly interpolate and renormalize probabilities, then sample the action. Paired comparison with direct execution of the same policy on identical seeds; 10,000 bootstrap resamples. Reproduction: `scripts/grid_loss.py`, `scripts/grid_loss_aligned.py`; data: `runs/20260920T013107_grid-loss/`, `runs/20260920T013344_grid-loss-aligned/`.

Grids A–D use uniform nodes on [0, 1]. Grids E–H (“aligned”) follow environment structure: sugar {0, 0.2, 0.4, 0.6, 0.8, 1}, bitter {0, 0.1, 0.3, 0.65, 1} (the environment never generates sugar ∈ (0, 0.2) or bitter ∈ (0.1, 0.3)); looming and hunger remain uniform. Format: sugar × bitter × looming × hunger.

## Oracle (direct: 151.2 trials)

| Grid | Points | Table lifetime | Difference from direct [95% CI] | Retained |
|---|---|---|---|---|
| A 5x3x5x3 | 225 | 60.1 | -91.2 [-98.9, -83.8] | 39.7% |
| B 7x5x7x5 | 1,225 | 111.1 | -40.1 [-47.0, -33.3] | 73.5% |
| C 9x5x9x5 | 2,025 | 116.8 | -34.5 [-41.1, -28.0] | 77.2% |
| D 11x5x11x9 | 5,445 | 132.9 | -18.3 [-24.0, -12.7] | 87.9% |
| E aligned 6x5x5x3 | 450 | 64.3 | -86.9 [-94.5, -79.5] | 42.5% |
| F aligned 6x5x11x5 | 1,650 | 121.3 | -29.9 [-36.0, -23.8] | 80.2% |
| G aligned 6x5x21x9 | 5,670 | 142.5 | -8.7 [-12.8, -4.7] | 94.2% |
| H aligned 6x5x41x17 | 20,910 | 144.6 | -6.6 [-10.5, -2.8] | 95.6% |

## fixed_priority (direct: 75.3 trials)

| Grid | Points | Table lifetime | Difference from direct [95% CI] | Retained |
|---|---|---|---|---|
| A 5x3x5x3 | 225 | 32.8 | -42.6 [-46.7, -38.7] | 43.5% |
| B 7x5x7x5 | 1,225 | 40.8 | -34.5 [-38.2, -30.9] | 54.2% |
| C 9x5x9x5 | 2,025 | 46.7 | -28.6 [-32.1, -25.3] | 62.0% |
| D 11x5x11x9 | 5,445 | 51.2 | -24.1 [-27.5, -20.9] | 68.0% |
| E aligned 6x5x5x3 | 450 | 32.1 | -43.2 [-47.3, -39.3] | 42.6% |
| F aligned 6x5x11x5 | 1,650 | 51.8 | -23.5 [-26.8, -20.3] | 68.7% |
| G aligned 6x5x21x9 | 5,670 | 62.3 | -13.0 [-15.6, -10.7] | 82.7% |
| H aligned 6x5x41x17 | 20,910 | 68.2 | -7.2 [-9.2, -5.2] | 90.5% |

## Measurements

- The default specified grid (A, 225 points) retains 40% of oracle survival and 43% of `fixed_priority` survival. The tabulated oracle on grid A (60.1) survives less than direct `fixed_priority` (75.3).
- All differences are significant (CI excludes zero), including the 20,910-point grid.
- Looming resolution gives the largest improvement: E → F (5 → 11 looming nodes) raises oracle retention from 43% to 80%.
- At nodes the table reproduces the policy exactly (verified by tests); loss occurs between nodes, where interpolating neighboring one-hot probabilities produces an action mixture that is then sampled.
- Both tested policies are deterministic (probabilities 0 or 1). Loss for smoothly varying probabilities (e.g. the Jev slice in `reports/probe_jev.md`) **was not measured** in this initial comparison.

## Dependence on policy sharpness (“soft oracle”)

Policy P(action) ∝ exp(Q / τ), where Q is the oracle value in expected remaining trials. τ → 0 gives the deterministic oracle; larger τ smooths probabilities. Node probabilities are exact (1 repetition). Data: `runs/20260920T013823_grid-loss-smooth/`; script `scripts/grid_loss_smooth.py`. For reference, Jev (`naive`) `p_escape` at the same looming points 0.2 / 0.4 / 0.5 / 0.6 / 0.8 is 0.03 / 0.16 / 0.26 / 0.46 / 0.67.

| τ | p_escape at looming 0.2 / 0.4 / 0.5 / 0.6 / 0.8 (sugar 0.6, bitter 0.05, hunger 0.5) | Direct lifetime, trials | Grid A: lifetime (retained) | Grid F | Grid G |
|---|---|---|---|---|---|
| 0.5 | 0.0 / 0.694 / 1.0 / 1.0 / 1.0 | 145.7 | 54.2 (37%) | 112.9 (77%) | 131.9 (91%) |
| 2.0 | 0.008 / 0.46 / 0.996 / 1.0 / 1.0 | 115.4 | 44.5 (39%) | 83.9 (73%) | 100.1 (87%) |
| 8.0 | 0.174 / 0.367 / 0.743 / 0.952 / 0.993 | 50.6 | 29.9 (59%) | 40.2 (79%) | 43.3 (86%) |
| 32.0 | 0.291 / 0.342 / 0.443 / 0.59 / 0.725 | 22.6 | 20.7 (91%) | 21.4 (94%) | 21.4 (95%) |

- On the specified grid (A), a sharp policy (τ = 0.5) retains 37% of survival; a smooth policy (τ = 32) retains 91%. Table-mode losses differ severalfold between sharp and smooth arbiters.
- Direct execution, without tables: smoothing the same value function reduces lifetime from 145.7 (τ = 0.5) to 22.6 trials (τ = 32); `random` achieves 14.1 on the same seeds. Under SPEC §4, actions are sampled from probabilities.

## Estimated grid costs for project arbiters (using earlier timings)

| Grid | Points | Connectome simulations at N_rep 20 | Jev calls at 3 modes × N_rep 10 | Jev sequentially at 0.4 s |
|---|---|---|---|---|
| A | 225 | 4 500 | 6 750 | 0.8 h |
| F | 1 650 | 33 000 | 49 500 | 5.5 h |
| G | 5 670 | 113 400 | 170 100 | 18.9 h |
| H | 20 910 | 418 200 | 627 300 | 69.7 h |

Connectome simulations with looming input in `reports/probe_looming.md` take 0.9–9.6 s per trial (without early stopping), versus 0.174 s for sugar-only trials.
