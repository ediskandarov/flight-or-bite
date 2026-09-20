# Evaluation on the `dev` split

Generated 2026-09-20T13:12:18+04:00 by `fob eval --split dev`; 1000 episodes, paired on seeds; raw data in `runs/20260920T131217_eval-dev`. Bootstrap: 10 000 resamples over episodes.
Lifetime = trials completed alive, censored at the episode limit. No deadline.

| Arbiter | Mean lifetime [95% CI] | Median | % of oracle | Mean energy | Final energy | EAT / ESCAPE / IDLE share | t_wall p50, µs |
|---|---|---|---|---|---|---|---|
| `random` | 14.7 [13.9, 15.5] | 11 | 0.0% | 41.8 | 33.4 | 38% / 28% / 34% | 1.2 |
| `fixed_priority` | 62.9 [60.1, 65.8] | 56 | 79.6% | 38.8 | 25.3 | 17% / 21% / 61% | 0.5 |
| `oracle` | 75.2 [72.8, 77.8] | 71 | 100.0% | 31.8 | 12.9 | 17% / 31% / 52% | 9.3 |

Causes of death (share of episodes):

| Arbiter | predator | starvation | toxin | missed deadline | censored (alive) |
|---|---|---|---|---|---|
| `random` | 92.8% | 6.2% | 1.0% | 0.0% | 0.0% |
| `fixed_priority` | 71.8% | 28.2% | 0.0% | 0.0% | 0.0% |
| `oracle` | 71.6% | 28.4% | 0.0% | 0.0% | 0.0% |

Paired differences in mean lifetime (a win only if the CI excludes zero):

| Comparison | Difference | 95% CI | Significant |
|---|---|---|---|
| fixed_priority - random | +48.2 | [+45.5, +51.0] | yes |
| oracle - random | +60.5 | [+58.0, +63.2] | yes |
| oracle - fixed_priority | +12.3 | [+10.0, +14.7] | yes |

Oracle's margin over `fixed_priority`: **16.4%** of the oracle's lifetime (SPEC §11 asks for a proposal to change the environment if it is below 10%: not the case).
