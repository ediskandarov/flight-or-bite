# Decisions log

Human decisions that refine or deviate from `SPEC.md`. The spec itself is not edited; where this
file and the spec disagree, this file wins. Each entry: date, decision, rationale, effect.

## 2026-09-19 — end of M0 (all recommendations in `open_questions.md` accepted)

| # | Decision | Effect |
|---|---|---|
| D1 | **Jev stays the main arbiter** (SPEC design unchanged). Reached through OpenRouter's alpha Decisions endpoint, since direct TypeSafe access is invite-only. Gemini 3.7 Flash as an extra "LLM" baseline is optional and deferred | No change to RQ1–RQ5. Jev's `t_wall` includes the OpenRouter hop; the report says so |
| D2 | **`N_rep = 20` for Jev** policy tables — Jev was observed to be non-deterministic | Deviates from SPEC §4.5 (450 calls → 9,000). All repeats are stored; the cache never deduplicates by request bytes. Gives the noise floor for the live-vs-table check (SPEC §7) |
| D3 | OpenRouter's per-generation `latency` is collected **after** timed runs and reported as **`t_gateway`**, never as `t_server` | `Decision.t_server_ms` stays `None` for Jev (SPEC §6.1 unchanged); `t_gateway` is an additional, clearly named column |
| D4 | Connectome version: **783 provisionally**, final choice at M1 after reading the paper and `model.py` | See M1 notes |
| D5 | Decision-grade measurements (backend choice, grid size, `latency bench`) are **re-run by the human** from their own terminal, on AC power, under `caffeinate -i`. The agent's runs are for development. `fob perf` records a throttling self-check | Applies to M1 and M4 |
| D6 | Python **3.12** | — |
| D7 | A third, preregistered Jev state mode **`bucketed`** (numbers → named levels) joins `naive` and `informed`. Bucket boundaries are fixed before any data is seen and go to `ENGINEERED.md` | Deviates from SPEC §4.3 (2 modes → 3). Jev table: 225 × 3 × 20 = 13,500 calls |
| D8 | **`--max-calls` default 100,000** (SPEC: 30,000), counter to persist across runs (due M4) | Money is not the constraint (~$1.40 per 100k calls) |
| D9 | The expected response `model` (`typesafe/jev-1.13-20260917`) is pinned in config and in `PREREG.md` hashes; a different value aborts the run. The alpha status of the endpoint is accepted as a risk and listed under limitations | Due M4 |

## 2026-09-20 — SPEC §6 simplified (human instruction)

| # | Decision | Effect |
|---|---|---|
| D10 | **Time is measured on the client only.** Every arbiter reports `t_wall`; the connectome additionally reports `t_sim`. | `Decision.t_server_ms` is removed. SPEC §6.1 shrinks to two quantities. Analysis 6.3-A is a `t_wall` table (plus `t_sim` and RTF for the connectome) |
| D11 | **Removed from SPEC §4.3 / §6.2:** `t_server`; the connect / first-byte / total breakdown; the 8-parallel-requests throughput test; network metadata (Wi-Fi/cable, city, time of day); any measurement through TypeSafe's direct API | `JevClient` has no trace hooks and no backend switch. **Supersedes D3** (`t_gateway` from OpenRouter's generation metadata is not collected) |
| D12 | **OpenRouter is the main and only access path** to Jev (`POST /api/alpha/decisions`, key `OPENROUTER_API_KEY`) | `JEV_API_KEY` / `TYPESAFE_API_KEY` are no longer read. Jev's `t_wall` includes the OpenRouter hop by design; the report states it. The endpoint's alpha status stays a listed limitation |
| D13 | **Model pinned: `jev-1.13`** — requested as `typesafe/jev-1.13`. OpenRouter answers with a dated snapshot (`typesafe/jev-1.13-20260917` today); any reply from outside the `jev-1.13` family raises `JevModelMismatch` and aborts the run. The exact snapshot id is logged per call | **Refines D9**: the pin is the family, not one dated snapshot; a snapshot change inside the family is recorded, not fatal |
| D14 | Latency is reported as **p50 / p95** (SPEC: p50 / p90 / p99) | `summarize_ns`, `fob jev smoke`, later `fob latency show` and `fob live` |
| D15 | **Kept as in the SPEC:** cache forcibly off in every timed run and `cache_hit = true` never enters latency statistics; chronometric curves (6.3-C); deadline sweep with both tracks (6.3-D); the speed-vs-quality figure (6.3-B) | — |

Not mentioned in the instruction and therefore left as in the SPEC until told otherwise: the
20-call warm-up with the cold first call reported separately; sequential calls over one
keep-alive session; the ECDF figure; the power-source / timer-throttling self-check of `fob perf`
(it describes the machine, not the network).

## 2026-09-20 — M1 accepted

| # | Decision | Effect |
|---|---|---|
| D16 | **M1 accepted. LIF backend: `event`** (NumPy + Numba). Brian2 stays as the reference in the test suite; the PyTorch backends stay as measured and rejected candidates | — |
| D17 | **Connectome: v783** (final; supersedes the provisional D4) | v630 remains downloadable for cross-checks only |
| D18 | Before M2: an **exploratory probe of the looming channel** (`reports/probe_looming.md`), 1–2 hours, nothing tuned, stop after the report. Everything in it is labelled exploratory (SPEC §8) | Not a milestone; does not count as G3 or G7 |
| D19 | Raw Jev responses are logged to disk from now on, before any new call is made | Closes the gap noted in `reports/status.md` §7 |

## 2026-09-20 (night) — "Proceed with implementation. I trust your judgement."

Human instruction received while the looming probe was running; it supersedes "stop after the
report" (D18). What the agent did with that latitude, and what it deliberately did not:

| # | Decision (agent's judgement, open to reversal) | Reason |
|---|---|---|
| D20 | **M2 implemented** (environment with deadline, baselines, oracle, `fob eval`) | Fully specified by numbers in SPEC §3–§4.4; depends on none of the open questions |
| D21 | **No choice of `R_max`, `theta_eat`, `alpha`, or of a different looming encoding** | These are the most influential hand-set parameters; the probe (`reports/probe_looming.md`) was commissioned so that the spec's author can decide them, and its findings (DNp01 fires in 100% of trials from looming 0.1) make the choice non-trivial |
| D22 | **Draft v0 Jev prompts written blind and committed before any call** (`713fe97`), then a 300-call exploratory probe (`reports/probe_jev.md`, $0.006) | The spec's author had asked for the exact requests, a `p_escape` slice and the spread over repeats and got "no data"; drafting blind keeps decision D7's condition (bucket boundaries fixed before data). Templates were not edited after the data came in |
| D23 | **Policy-table machinery, call ledger (D8), degree- and sign-preserving shuffle, `fob table` / `fob replay`** implemented; **no Jev or connectome table was built** | All fully specified and parameter-free. Building real tables would spend hours on draft prompts and an undefined decoder |
| D24 | Exploratory measurements with the oracle as a stand-in (`reports/grid_loss.md`) | The oracle is not an object of study, so probing the tabular mode with it tunes nothing about the comparison |

## 2026-09-20 — the spec author's decisions on `open_questions.md` (N1–N5)

| # | Decision | Effect |
|---|---|---|
| D25 | **Calibration, per channel: 50% response at stimulus 0.5.** `theta_eat` = half of MN9's saturation rate, sliding window 50 ms. `R_max` of the sugar and of the looming channel found separately by bisection on single stimuli, dev seeds. `R_max` of the bitter channel = `R_max` of sugar. DNp01 decoder: one spike. Everything into `ENGINEERED.md` | Supersedes the provisional E1 (`R_max` = 200 Hz for every channel). Answers N1 and Q4 |
| D26 | After calibration: repeat the N2 measurement (suppression of MN9 by looming, slice sugar 0.6) on the real graph and on **20 shuffled graphs** -> `reports/probe_interaction.md`. **Stop after it** | Exploratory; not G4/G7 |
| D27 | **Main metric: online, native action.** Connectome: the outcome of one simulation; Jev: the response's `choice` field; oracle: argmax. Sampling the action from `probs` becomes a secondary analysis. **T3 is cancelled.** 300 paired episodes. Jev runs online only in its main state mode, which is chosen on dev. Policy tables serve RQ3/RQ4 only, on **grid B** (7 x 5 x 7 x 5) | Deviates from SPEC §4 ("action sampled from probs"), §7 (1000 tabular episodes as the main metric) and §4.5 (default grid). Answers N3 and N3a |
| D28 | **Environment sweep on dev:** `p_food` in {0.3, 0.4} x `eat_gain` in {8, 10}; the target is a configuration where 25-75% of the oracle's deaths are from starvation. The agent shows the table and does **not** choose. **Stop after it** | `reports/env_sweep.md`. Answers N5 |
| D29 | Jev: a fourth state mode **`informed_bucketed`** (2 x 2 design: rules yes/no x numbers/levels) | Deviates further from SPEC §4.3 (2 modes -> 4) |
| D30 | Shiu et al. 2024 and the neuroai.science article are to be read before the gates are implemented | Already done on 2026-09-20; notes in `reports/probe_looming.md` §1 |

## 2026-09-20 — the author's decisions after `env_sweep`, `calibration`, `probe_interaction`

| # | Decision | Effect |
|---|---|---|
| D31 | **Environment: `p_food` 0.3, `eat_gain` 8, `escape_cost` 1** (other values as in SPEC §3) | Deviates from SPEC §3. In `reports/env_sweep.md` this configuration gave: oracle 75.2 trials, 28% of its deaths from starvation, 16% margin over `fixed_priority`. The `informed` prompt texts carry the new numbers |
| D32 | **`alpha` = 1.0** | E11. Calibration stays anchored at hunger = 0 |
| D33 | **Bitter GRNs: the 20 of the model authors' list** | E12 |
| D34 | `theta_eat` kept; its justification in `ENGINEERED.md` rewritten as "a burst criterion, chosen by us". Tie rule (R7) accepted | E9, E10 |
| D35 | Exploratory probe `reports/probe_r5.md` with a pre-specified test (paired McNemar on "DNp01 spiked", identical seeds, 40 repeats, looming 0.6 / 0.8 / 1.0): specificity, dose, mediators, alternative looming encoding. Nothing tuned. **Stop after the report** | Protocol committed before the run |
