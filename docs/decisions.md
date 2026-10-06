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

## 2026-09-20 — `probe_r5` accepted, exploration closed

| # | Decision | Effect |
|---|---|---|
| D36 | **Encoding frozen:** rate code, `R_max` sugar 102.8 Hz, looming 2.34 Hz, `theta_eat` = 4 spikes / 50 ms, `alpha` 1.0. The population (fraction-of-neurons) code is used only as a robustness check in G6 | `configs/encoding.yaml` |
| D37 | **M3: formal gates G1-G7.** G5 additionally ablates `M_loom` (25 neurons) and the single cL20. G7 = paired McNemar as in `probe_r5` | `configs/gates.yaml` fixed and committed before the gates are run |
| D38 | **Draft of `PREREG.md`** with confirmatory hypotheses on fresh seeds, Holm across levels: H1 sugar 0.6 lowers P(DNp01); H2 monotone in dose; H3 silencing `M_loom` removes the effect; H4 hunger 1 vs 0 at sugar 0.6 lowers P(ESCAPE); H5 shift of the escape curve by sugar in Jev: sign and size against the oracle | Kept as `PREREG.draft.md`: a file named `PREREG.md` would unlock the test split |
| D39 | Random sensory set 5 and the targets through which `M_loom` acts are **not** investigated; they go under "not established" | — |
| D40 | The Jev templates are sent to the author for review before M4. **Stop after M3 and the PREREG draft** | — |

## 2026-09-20 — M3 accepted

| # | Decision | Effect |
|---|---|---|
| D41 | **M3 accepted. G6 stands as a failure.** The final report carries SPEC §5's sentence verbatim — "выводы зависят от ручных параметров" — plus the clarification: both failed variants are a weakening by x0.5, the network is silent, there is no change of sign | `reports/gates.md`, `PREREG.md` §6. No threshold was changed after the results |
| D42 | Wording. **cL20:** ablation does not remove the effect; its targets on this path (LC4 / LPLC2) are clamped sources in the model, so the path is invisible by construction; the mechanism is carried by the other 24 neurons. **G4:** "on the shuffled graphs the signal does not reach the output neurons" | Checked against data before being written down: 345 of cL20's 361 synapses onto looming-active DNp01 partners land on LC4 (343) / LPLC2 (2); the stimulated neurons' spikes are identical with and without sugar (0 differing pairs of 17 916); ablating the other 24 with cL20 intact removes the effect (34 -> 0). `runs/cl20_check.json` |
| D43 | Spike-for-spike check of `event` against Brian2 on 10 conflict trials (sugar 0.6 + looming 0.8, frozen encoding, identical input) | `reports/crosscheck_brian2.md` |
| D44 | `PREREG.md` gains a planned robustness analysis of H1 (r_max x1.5, w_syn x1.5, alpha 0.5 / 1.5, theta 3 / 5 spikes, population code); the x0.5 variants are reported as "the network is silent" | `PREREG.md` §4. The file is named `PREREG.md` with `Status: DRAFT`; the test split opens only on a `Status: FROZEN` line of its own plus matching hashes (`src/flight_or_bite/prereg.py`) |
| D45 | Texts of all Jev templates in `reports/jev_templates.md`. **M4 does not start until the author approves them** | — |

## 2026-09-20 — Jev templates approved as v1

| # | Decision | Effect |
|---|---|---|
| D46 | **Templates accepted with edits as v1, not tuned on dev.** (1) hunger sentence: "hunger = 1 − (energy / 100): 0 means full energy, 1 means about to starve."; (2) "ESCAPE costs an additional 1 energy." / "IDLE has no additional cost."; (3) one question in all four modes: "Which action should the agent take on this trial?"; (4) the "rules" factor is a package (rules + `criteria` descriptions) and is not split; (5) the rules go into `instructions` before the question, `state` carries the observation only; `docs/jev_api_notes.md` §12 shows the full request body of each mode | `configs/jev_prompts/*.yaml`, `reports/jev_templates.md`. Supersedes the v0 drafts; `reports/probe_jev.md` was made with v0 and the old environment |
| D47 | In the bucketed modes only unique combinations of levels are queried (900 of 1 225 points on grid B); the rest are copies flagged `cache_hit` | `policy_table/table.py` (`key_fn`) |
| D48 | Jev latency is reported per state mode, separately | `PREREG.md` §8 |
| D49 | Order: Brian2 cross-check on conflict trials -> choose Jev's main mode on 50 dev episodes -> show the final PREREG to the author -> freeze -> test | — |

## 2026-09-20 — edits to PREREG.md before the freeze

| # | Decision | Effect |
|---|---|---|
| D50 | **H6:** the primary test is a paired Wilcoxon test on `t_sim` of the first DNp01 spike (H1 pairs with a spike in both arms, sugar 0.6 vs looming-only). The correlation with difficulty d is secondary: IDLE trials excluded, only grid points with p_eat + p_escape >= 0.5. For Jev an equivalence claim: the 95% CI of rho inside [-0.1, 0.1] | `PREREG.md` §8 |
| D51 | **Deadline sweep:** the share of decisions made within the deadline, from the measured latency distributions, both tracks; survival under a deadline is not simulated | Deviates from SPEC §6.3-D |
| D52 | H1-H4 and the robustness analysis: **100 pairs per level** | — |
| D53 | H5: `Delta_oracle` computed and written in before the freeze: **-0.0909 (-1/11), negative** | — |
| D54 | Jev tables: **two passes of N_rep 5, at least 12 h apart**, with a `session` column | Table builder to be extended in M4 |
| D55 | Secondary `sample_from_probs` analysis: 100 episodes. **Jev failure policy** written into `PREREG.md` §2b: no decision is ever substituted; retries for transient errors; otherwise the run stops and the unfinished episode is replayed from its start | The test harness must implement the episode replay |
| D56 | §2: the main comparison is **connectome vs jev_informed**. H4 gets the additional outcome "DNp01 spiked". Duplicate `cache_hit` sentence removed | — |
| D57 | After the edits the diff is shown to the author; **the freeze happens only on the author's word** | `PREREG.md` stays `Status: DRAFT` |

## 2026-09-20 — PREREG.md accepted and frozen

| # | Decision | Effect |
|---|---|---|
| D58 | **`PREREG.md` accepted by the author in full** (text of `2209e6a`, edits D50-D57). Freeze ordered by the author: smoke run of the full test command on dev (5 episodes, all arbiters) -> final header -> hashes recomputed -> `Status: FROZEN` -> commit | Smoke: `runs/online_smoke/`, 25 of 25 episodes finished, 252 Jev calls. At the freeze only the header, the spent-calls figure in §9 (9 091 -> 9 343) and §11 (commit id, 14 hashes: `configs/confirm.yaml` and `configs/timing.yaml` added, `configs/grid.yaml` changed by D54) were edited |
| D59 | **Division of labour after the freeze.** The author runs from their own terminal: the main online run on `test`, the secondary `sample_from_probs` run, every latency measurement (`reports/run_instructions.md`). The agent computes: H1-H4, H6 (primary test), the robustness analysis of H1, the connectome table, the Jev tables (pass 1 now, pass 2 not earlier than 12 h later), then `fob report`. Nothing is interpreted beyond `PREREG.md`; everything else goes under exploratory. No new probes | — |

Agent's judgement, open to reversal:

| # | Decision | Reason |
|---|---|---|
| D60 | The uncommitted work of the interrupted session was split into a formatting-only commit (`7fcdf8b`, ruff line-length 100 -> 120) and the substantive commits | The author was asked and did not object; the split keeps the substantive diff reviewable. No hashed file is touched by the formatter |
| D61 | **H5 is computed by the agent** together with H1-H4 (`fob confirm-h5`, 440 Jev calls, budgeted in `PREREG.md` §9), although the author's list in D59 does not name it | H5 is preregistered and is not a latency measurement, so nothing about it needs the author's terminal |
| D62 | `fob confirm` and `fob confirm-h5` refuse to run unless `PREREG.md` is frozen with matching hashes, and refuse to run a second time once their result file exists | "Confirmatory analyses are computed once" is enforced by code, not by memory |

## 2026-10-06 — author requests a direct TypeSafe API test

| # | Decision | Effect |
|---|---|---|
| D63 | User explicitly requested testing Jev without OpenRouter and supplied TYPESAFE_API_KEY. User reported an opening TypeSafe balance of $5.00 and requested spend tracking. | Direct access is authorized for this separate exploratory check, superseding D11–D12 only for that scope. The frozen main experiment still uses OpenRouter. Per-call token usage and public-rate estimated cost are recorded separately in reports/direct_typesafe; all attempts also count toward the project-wide 100,000-call cap. No provider balance is inferred to be verified. |
