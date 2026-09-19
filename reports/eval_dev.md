# Evaluation on the `dev` split

Generated 2026-09-20T01:21:44+04:00 by `fob eval --split dev`; 1000 episodes, paired on seeds; raw data in `runs/20260920T012140_eval-dev`. Bootstrap: 10 000 resamples over episodes.
Lifetime = trials completed alive, censored at the episode limit. No deadline.

| Arbiter | Mean lifetime [95% CI] | Median | % of oracle | Mean energy | Final energy | EAT / ESCAPE / IDLE share | t_wall p50, µs |
|---|---|---|---|---|---|---|---|
| `random` | 14.1 [13.4, 14.8] | 11 | 0.0% | 41.1 | 31.4 | 37% / 29% / 33% | 6.8 |
| `fixed_priority` | 75.3 [71.0, 79.9] | 52 | 44.6% | 60.8 | 66.4 | 30% / 21% / 49% | 6.7 |
| `oracle` | 151.2 [143.4, 159.3] | 114 | 100.0% | 46.9 | 35.4 | 27% / 33% / 40% | 16.3 |

Causes of death (share of episodes):

| Arbiter | predator | starvation | toxin | missed deadline | censored (alive) |
|---|---|---|---|---|---|
| `random` | 85.7% | 13.3% | 1.0% | 0.0% | 0.0% |
| `fixed_priority` | 98.0% | 1.8% | 0.0% | 0.0% | 0.2% |
| `oracle` | 92.9% | 3.3% | 0.0% | 0.0% | 3.8% |

Paired differences in mean lifetime (a win only if the CI excludes zero):

| Comparison | Difference | 95% CI | Significant |
|---|---|---|---|
| fixed_priority - random | +61.2 | [+56.8, +65.6] | yes |
| oracle - random | +137.1 | [+129.3, +145.4] | yes |
| oracle - fixed_priority | +75.9 | [+68.4, +83.6] | yes |

Oracle's margin over `fixed_priority`: **50.2%** of the oracle's lifetime (SPEC §11 asks for a proposal to change the environment if it is below 10%: not the case).

Deadline sweep, `wall` track — mean lifetime:

| deadline, ms | `random` | `fixed_priority` | `oracle` |
|---|---|---|---|
| 1 | 14.1 | 75.3 | 151.2 |
| 3 | 14.1 | 75.3 | 151.2 |
| 10 | 14.1 | 75.3 | 151.2 |
| 30 | 14.1 | 75.3 | 151.2 |
| 100 | 14.1 | 75.3 | 151.2 |
| 300 | 14.1 | 75.3 | 151.2 |
| 1000 | 14.1 | 75.3 | 151.2 |
| 3000 | 14.1 | 75.3 | 151.2 |

Deadline sweep, `native` track — mean lifetime:

| deadline, ms | `random` | `fixed_priority` | `oracle` |
|---|---|---|---|
| 1 | 14.1 | 75.3 | 151.2 |
| 3 | 14.1 | 75.3 | 151.2 |
| 10 | 14.1 | 75.3 | 151.2 |
| 30 | 14.1 | 75.3 | 151.2 |
| 100 | 14.1 | 75.3 | 151.2 |
| 300 | 14.1 | 75.3 | 151.2 |
| 1000 | 14.1 | 75.3 | 151.2 |
| 3000 | 14.1 | 75.3 | 151.2 |
