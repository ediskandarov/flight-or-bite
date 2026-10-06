# Jev probe with draft v0 templates (exploratory)

Date: 2026-09-20. Exploratory run (SPEC §8), not a policy table or §6.2 protocol benchmark. Request templates were committed **before** their first call (`713fe97`); bucket boundaries were chosen before observing responses. Nothing was tuned; templates were not changed after viewing these data.

Model requested: `typesafe/jev-1.13`; all 300 responses returned `typesafe/jev-1.13-20260917`. Run cost: $0.00592. Raw exchanges: `runs/jev_raw/20260920.jsonl` (300 lines); summaries: `runs/20260920T012605_probe-jev/probe.json`. Reproduction: `uv run python scripts/probe_jev.py`.

Slice: sugar = 0.6, bitter = 0.05, hunger = 0.5 (background for the connectome conflict slice in `reports/probe_looming.md` §5), looming 0 to 1. 20 identical requests at 0.2 / 0.5 / 0.8, and 5 at other points.

## 1. Exact requests (HTTP body, looming = 0.5)

Template files: `configs/jev_prompts/{naive,informed,bucketed}.yaml`. Observation values rounded to 2 decimals. `bucketed` uses five equal-width levels: [0, 0.2) very low, [0.2, 0.4) low, [0.4, 0.6) medium, [0.6, 0.8) high, [0.8, 1] very high; exactly 0 → none. `bucketed` is `naive` with numbers replaced by words (no environment rules), keeping a single difference from `naive`.

**naive** (template SHA-256 `9cfb1e2a6335561d…`):

```json
{"model":"typesafe/jev-1.13","questions":{"action":{"criteria":{"EAT":null,"ESCAPE":null,"IDLE":null},"instructions":"Which action should the agent take?","type":"choice"}},"state":{"bitter":0.05,"hunger":0.5,"looming":0.5,"sugar":0.6}}
```

**informed** (template SHA-256 `ddfdc346007df9c7…`):

```json
{"model":"typesafe/jev-1.13","questions":{"action":{"criteria":{"EAT":"Eat the food that is present on this trial.","ESCAPE":"Flee from a possible predator.","IDLE":"Do nothing on this trial."},"instructions":"Which action should the agent take on this trial?","type":"choice"}},"state":{"observation":{"bitter":0.05,"hunger":0.5,"looming":0.5,"sugar":0.6},"rules":"An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four numbers between 0 and 1 and takes one action. `sugar` is the amount of food present; 0 means there is no food. Food is present on 50% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. `hunger` equals 1 minus energy divided by 100. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 12 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs 3 energy. A predator cannot kill an agent that escapes. IDLE costs nothing extra. If a predator is present, an idle agent dies with probability 0.3."}}
```

**bucketed** (template SHA-256 `acebaa97f3453c59…`):

```json
{"model":"typesafe/jev-1.13","questions":{"action":{"criteria":{"EAT":null,"ESCAPE":null,"IDLE":null},"instructions":"Which action should the agent take?","type":"choice"}},"state":{"bitter":"very low","hunger":"medium","looming":"medium","sugar":"high"}}
```

## 2. p_escape slice over looming

Probabilities as returned by the API, renormalized to sum to one. Raw sums across 300 responses: 0.99–1.0 (0.99 in 2 responses; 1.0 in 298).

**naive**

| looming | n | p_escape: mean (SD) [min–max] | p_eat: mean (SD) | p_idle: mean | argmax |
|---|---|---|---|---|---|
| 0.0 | 5 | 0.002 (0.004) [0.00–0.01] | 0.914 (0.010) | 0.084 | EAT 5 |
| 0.1 | 5 | 0.016 (0.005) [0.01–0.02] | 0.938 (0.012) | 0.046 | EAT 5 |
| 0.2 | 20 | 0.030 (0.009) [0.02–0.05] | 0.928 (0.013) | 0.042 | EAT 20 |
| 0.3 | 5 | 0.082 (0.023) [0.06–0.11] | 0.890 (0.021) | 0.028 | EAT 5 |
| 0.4 | 5 | 0.156 (0.033) [0.12–0.20] | 0.818 (0.028) | 0.026 | EAT 5 |
| 0.5 | 20 | 0.261 (0.022) [0.22–0.30] | 0.710 (0.022) | 0.030 | EAT 20 |
| 0.6 | 5 | 0.458 (0.029) [0.41–0.50] | 0.518 (0.026) | 0.024 | EAT 4, ESCAPE 1 |
| 0.7 | 5 | 0.584 (0.042) [0.52–0.65] | 0.406 (0.042) | 0.010 | ESCAPE 5 |
| 0.8 | 20 | 0.668 (0.026) [0.62–0.72] | 0.322 (0.026) | 0.010 | ESCAPE 20 |
| 0.9 | 5 | 0.746 (0.019) [0.71–0.76] | 0.246 (0.017) | 0.008 | ESCAPE 5 |
| 1.0 | 5 | 0.742 (0.007) [0.73–0.75] | 0.248 (0.007) | 0.010 | ESCAPE 5 |

**informed**

| looming | n | p_escape: mean (SD) [min–max] | p_eat: mean (SD) | p_idle: mean | argmax |
|---|---|---|---|---|---|
| 0.0 | 5 | 0.016 (0.008) [0.01–0.03] | 0.958 (0.015) | 0.026 | EAT 5 |
| 0.1 | 5 | 0.022 (0.004) [0.02–0.03] | 0.932 (0.007) | 0.046 | EAT 5 |
| 0.2 | 20 | 0.035 (0.007) [0.02–0.05] | 0.896 (0.014) | 0.069 | EAT 20 |
| 0.3 | 5 | 0.094 (0.010) [0.08–0.11] | 0.818 (0.021) | 0.088 | EAT 5 |
| 0.4 | 5 | 0.190 (0.025) [0.16–0.22] | 0.700 (0.038) | 0.110 | EAT 5 |
| 0.5 | 20 | 0.324 (0.030) [0.28–0.41] | 0.569 (0.033) | 0.107 | EAT 20 |
| 0.6 | 5 | 0.590 (0.030) [0.54–0.63] | 0.342 (0.033) | 0.068 | ESCAPE 5 |
| 0.7 | 5 | 0.650 (0.013) [0.63–0.66] | 0.302 (0.015) | 0.048 | ESCAPE 5 |
| 0.8 | 20 | 0.742 (0.030) [0.70–0.82] | 0.215 (0.028) | 0.044 | ESCAPE 20 |
| 0.9 | 5 | 0.806 (0.031) [0.77–0.86] | 0.154 (0.030) | 0.040 | ESCAPE 5 |
| 1.0 | 5 | 0.702 (0.040) [0.64–0.75] | 0.262 (0.035) | 0.036 | ESCAPE 5 |

**bucketed**

| looming | n | p_escape: mean (SD) [min–max] | p_eat: mean (SD) | p_idle: mean | argmax |
|---|---|---|---|---|---|
| 0.0 | 5 | 0.002 (0.004) [0.00–0.01] | 0.878 (0.023) | 0.120 | EAT 5 |
| 0.1 | 5 | 0.010 (0.000) [0.01–0.01] | 0.896 (0.015) | 0.094 | EAT 5 |
| 0.2 | 20 | 0.010 (0.000) [0.01–0.01] | 0.894 (0.014) | 0.096 | EAT 20 |
| 0.3 | 5 | 0.010 (0.000) [0.01–0.01] | 0.894 (0.016) | 0.096 | EAT 5 |
| 0.4 | 5 | 0.136 (0.016) [0.12–0.16] | 0.820 (0.017) | 0.044 | EAT 5 |
| 0.5 | 20 | 0.142 (0.022) [0.10–0.18] | 0.816 (0.022) | 0.043 | EAT 20 |
| 0.6 | 5 | 0.600 (0.033) [0.55–0.64] | 0.390 (0.033) | 0.010 | ESCAPE 5 |
| 0.7 | 5 | 0.578 (0.024) [0.55–0.62] | 0.412 (0.024) | 0.010 | ESCAPE 5 |
| 0.8 | 20 | 0.742 (0.030) [0.67–0.77] | 0.248 (0.030) | 0.010 | ESCAPE 20 |
| 0.9 | 5 | 0.728 (0.039) [0.67–0.78] | 0.262 (0.039) | 0.010 | ESCAPE 5 |
| 1.0 | 5 | 0.712 (0.052) [0.64–0.78] | 0.278 (0.052) | 0.010 | ESCAPE 5 |

## 3. Variation across identical repeated requests

| Mode | looming | n | SD p_eat | SD p_escape | SD p_idle | Distinct vectors |
|---|---|---|---|---|---|---|
| naive | 0.2 | 20 | 0.0135 | 0.0092 | 0.0081 | 11 of 20 |
| naive | 0.5 | 20 | 0.0220 | 0.0223 | 0.0022 | 9 of 20 |
| naive | 0.8 | 20 | 0.0258 | 0.0258 | 0.0000 | 10 of 20 |
| informed | 0.2 | 20 | 0.0139 | 0.0067 | 0.0109 | 10 of 20 |
| informed | 0.5 | 20 | 0.0332 | 0.0301 | 0.0131 | 16 of 20 |
| informed | 0.8 | 20 | 0.0284 | 0.0297 | 0.0065 | 13 of 20 |
| bucketed | 0.2 | 20 | 0.0139 | 0.0000 | 0.0139 | 6 of 20 |
| bucketed | 0.5 | 20 | 0.0222 | 0.0215 | 0.0094 | 16 of 20 |
| bucketed | 0.8 | 20 | 0.0304 | 0.0304 | 0.0022 | 11 of 20 |

## 4. Reference: oracle and fixed_priority at the same points

The oracle is deterministic (SPEC §4.4); threat posterior is Bayesian, inferred from looming.

| looming | P(threat \| looming) | Oracle action | fixed_priority action |
|---|---|---|---|
| 0.0 | 0.000 | EAT | EAT |
| 0.1 | 0.003 | EAT | EAT |
| 0.2 | 0.011 | EAT | EAT |
| 0.3 | 0.037 | EAT | EAT |
| 0.4 | 0.118 | ESCAPE | EAT |
| 0.5 | 0.318 | ESCAPE | EAT |
| 0.6 | 0.620 | ESCAPE | ESCAPE |
| 0.7 | 0.851 | ESCAPE | ESCAPE |
| 0.8 | 0.952 | ESCAPE | ESCAPE |
| 0.9 | 0.986 | ESCAPE | ESCAPE |
| 1.0 | 0.998 | ESCAPE | ESCAPE |

## 5. Timing (arbiter client t_wall: request construction + HTTP + parsing + sampling)

Sequential calls in one keep-alive session, from the agent's process at night; no warm-up, first call of each mode included. Not a §6.2 protocol benchmark.

| Mode | n | p50, ms | p95, ms | Min | Max |
|---|---|---|---|---|---|
| naive | 100 | 370.8 | 619.8 | 286.8 | 1342.9 |
| informed | 100 | 361.0 | 483.9 | 295.2 | 1539.6 |
| bucketed | 100 | 364.7 | 492.0 | 294.4 | 567.4 |
| all | 300 | 365.8 | 500.9 | 286.8 | 1539.6 |

## 6. Not included

- Other sugar, bitter, or hunger values; bitter slices; the full grid.
- Template tuning (draft v0; under SPEC §4.3, templates may be tuned only on `dev` and are frozen in `PREREG.md`).
- An informed + bucketed mode; whether to add it is an author decision.
- Jev survival evaluation in the environment (requires policy tables, milestone M4).
