# Environment parameter sweep on `dev` (decision D28)

Date: 2026-09-20. 1,000 `dev` episodes (seeds 0–999) per configuration; the oracle is **recomputed** for each configuration; other parameters follow SPEC §3. Native actions (D27): oracle and `fixed_priority` use argmax. Author's goal: 25–75% of oracle deaths caused by starvation. The implementer does **not** select a configuration. Script: `scripts/env_sweep.py`; data: `runs/20260920T103314_env-sweep/`.

Death fractions are computed among episodes ending in death (censored episodes excluded). G is `eat_gain` (energy gain = G · sugar).

## Requested table

| Configuration | p_food | G | Oracle: lifetime [95% CI] | Median | **Starvation, fraction of deaths** | Predator | Toxin | Survived to 500 | Mean energy | fixed_priority: lifetime | random: lifetime | Oracle lead over fixed | Within 25–75% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SPEC default | 0.5 | 12 | 151.2 [143.4, 159.4] | 114 | **3.4%** | 96.6% | 0.0% | 3.8% | 46.9 | 75.3 | 13.9 | 50.2% | no |
| p_food 0.3, G 8.0 | 0.3 | 8 | 45.5 [44.1, 47.0] | 44 | **18.3%** | 81.7% | 0.0% | 0.0% | 30.8 | 42.3 | 12.7 | 7.0% | no |
| p_food 0.3, G 10.0 | 0.3 | 10 | 54.4 [52.4, 56.5] | 49 | **14.7%** | 85.3% | 0.0% | 0.0% | 32.8 | 48.9 | 13.0 | 10.1% | no |
| p_food 0.4, G 8.0 | 0.4 | 8 | 55.6 [53.5, 57.7] | 51 | **12.1%** | 87.9% | 0.0% | 0.0% | 32.7 | 50.4 | 12.9 | 9.3% | no |
| p_food 0.4, G 10.0 | 0.4 | 10 | 74.2 [70.8, 77.7] | 62 | **9.0%** | 91.0% | 0.0% | 0.0% | 36.0 | 61.7 | 13.3 | 16.9% | no |

Additional results from the same runs:

| Configuration | Oracle: EAT / ESCAPE / IDLE fractions | fixed_priority: starvation fraction of deaths | random: starvation fraction of deaths |
|---|---|---|---|
| SPEC default | 27% / 33% / 40% | 1.8% | 10.1% |
| p_food 0.3, G 8.0 | 17% / 22% / 61% | 51.9% | 18.8% |
| p_food 0.3, G 10.0 | 17% / 24% / 59% | 43.6% | 16.6% |
| p_food 0.4, G 8.0 | 22% / 24% / 53% | 39.5% | 16.1% |
| p_food 0.4, G 10.0 | 23% / 26% / 51% | 24.0% | 14.1% |

Findings:

- None of the four requested configurations reaches the 25–75% range: oracle starvation deaths range from 9.0% to 18.3%; specification defaults give 3.4%.
- Oracle lead over `fixed_priority` (1 − L_fixed / L_oracle) ranges from 7.0% to 16.9% in requested configurations; specification defaults give 50.2%. M2 acceptance threshold in SPEC §11: 10%.

## Reference: neighboring configurations (not requested)

Same protocol; only the first-column parameter changes. Script: `scripts/env_sweep_extra.py`; data: `runs/20260920T103445_env-sweep-extra/`.

| Change from SPEC §3 | Oracle: lifetime | **Starvation, fraction of deaths** | Predator | Survived to 500 | fixed_priority: lifetime | Oracle lead over fixed | Within 25–75% |
|---|---|---|---|---|---|---|---|
| p_food = 0.2, eat_gain = 8 | 37.7 | **27.6%** | 72.4% | 0.0% | 35.2 | 6.6% | yes |
| p_food = 0.2, eat_gain = 10 | 41.8 | **25.0%** | 75.0% | 0.0% | 38.6 | 7.6% | yes |
| p_food = 0.3, eat_gain = 6 | 39.5 | **21.9%** | 78.1% | 0.0% | 36.7 | 7.0% | no |
| p_food = 0.3, eat_gain = 8, p_threat = 0.1 | 81.2 | **20.3%** | 79.7% | 0.0% | 71.8 | 11.6% | no |
| p_food = 0.3, eat_gain = 10, p_threat = 0.1 | 110.5 | **13.7%** | 86.3% | 0.4% | 99.4 | 10.1% | no |
| p_food = 0.4, eat_gain = 8, p_threat = 0.1 | 124.3 | **8.4%** | 91.6% | 0.7% | 109.0 | 12.3% | no |
| p_food = 0.4, eat_gain = 10, p_threat = 0.1 | 185.3 | **4.6%** | 95.4% | 7.8% | 141.4 | 23.7% | no |
| p_food = 0.3, eat_gain = 8, p_death_eat = 0.3, p_death_idle = 0.15 | 60.4 | **15.2%** | 84.8% | 0.0% | 50.0 | 17.2% | no |
| p_food = 0.4, eat_gain = 10, p_death_eat = 0.3, p_death_idle = 0.15 | 116.1 | **7.1%** | 92.9% | 1.0% | 93.2 | 19.8% | no |
| p_food = 0.3, eat_gain = 8, escape_cost = 1 | 75.2 | **28.4%** | 71.6% | 0.0% | 62.9 | 16.4% | yes |
| p_food = 0.4, eat_gain = 10, escape_cost = 1 | 186.2 | **9.8%** | 90.2% | 6.2% | 78.3 | 57.9% | no |
