# Selecting the primary Jev mode on `dev` (decision D49)

Date: 2026-09-20. Rule specified by the author before the run (`PREREG.md` §2): four modes play the same 50 dev episodes (seeds 0–49) online with native actions (`choice` field); select highest mean lifetime, breaking ties by fewer calls. Templates v1 were committed before the first call (`6c6f15c`) and not tuned on `dev`. Script: `scripts/select_jev_mode.py`; data: `runs/20260920T154550_select-jev-mode/selection.json`; raw exchanges: `runs/jev_raw/20260920.jsonl`. Environment: `configs/env.yaml` (D31). Every response used `typesafe/jev-1.13-20260917`.

| Mode | Lifetime, trials: mean [95% CI] | Median | Deaths: predator / starvation / toxin (out of 50) | EAT / ESCAPE / IDLE fractions | Calls | t_wall p50 / p95, ms |
|---|---|---|---|---|---|---|
| `naive` | 25.98 [20.6, 31.8] | 24 | 49 / 1 / 0 | 82% / 18% / 0% | 1,349 | 377 / 512 (n = 1,349) |
| `informed` **(primary)** | 64.26 [56.7, 72.3] | 63 | 9 / 41 / 0 | 17% / 55% / 27% | 3,263 | 377 / 511 (n = 3,263) |
| `bucketed` | 16.82 [13.2, 20.7] | 14 | 50 / 0 / 0 | 86% / 12% / 2% | 891 | 379 / 520 (n = 891) |
| `informed_bucketed` | 64.20 [53.4, 75.6] | 60 | 29 / 20 / 1 | 18% / 30% / 52% | 3,262 | 389 / 516 (n = 3,258) |
| `random` (direct) | 16.02 [12.2, 20.1] | 12 | 42 / 7 / 1 | 34% / 34% / 33% | — | — |
| `fixed_priority` (direct) | 56.44 [44.0, 70.1] | 48 | 37 / 13 / 0 | 18% / 22% / 61% | — | — |
| `oracle` (direct) | 77.60 [65.6, 90.7] | 68 | 32 / 18 / 0 | 17% / 30% / 52% | — | — |

**Primary mode selected by the rule: `informed`.**

Paired mean lifetime differences on the same 50 seeds (10,000 bootstrap resamples):

| Comparison | Difference | 95% CI | CI excludes zero |
|---|---|---|---|
| `informed` − `naive` | +38.3 | [+29.0, +47.8] | yes |
| `informed` − `bucketed` | +47.4 | [+39.6, +55.9] | yes |
| `informed` − `informed_bucketed` | +0.1 | [-6.6, +6.9] | no |
| `informed` − `random` | +48.2 | [+40.4, +56.6] | yes |
| `informed` − `fixed_priority` | +7.8 | [-3.5, +19.1] | no |
| `informed` − `oracle` | -13.3 | [-23.0, -3.8] | yes |

Findings:

- `informed` and `informed_bucketed` differ by 0.06 trials; the difference CI includes zero. The mean-based rule selects `informed`, but these modes are statistically indistinguishable on 50 episodes. Their action profiles differ: `informed` escapes in 55% of trials and mostly dies of starvation (41 of 50); `informed_bucketed` escapes in 30% and more often dies to predators (29 of 50).
- Both modes with the rules package survive 2.5–4 times longer than modes without it; rule-free modes perform at the `random` level (`bucketed`) or slightly above it (`naive`).
- Latency (client `t_wall`, sequential calls, one keep-alive session, agent process with concurrent local computation — **not a §8 protocol benchmark**): p50 377–389 ms across modes despite requests being tens of times longer with rules. Retried network calls: naive 0, informed 0, bucketed 0, informed_bucketed 4; excluded from latency statistics.
- Usage: 8,765 calls in this run; project total 9,091 of 100,000.
