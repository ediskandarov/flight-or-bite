# PREREG — preregistration

Status: FROZEN

> **English translation, 2026-10-06 (D65).** The author requested an English edition after all experiments were complete. This changes the language of the frozen document, not its scientific protocol. The original frozen text is preserved at commit `4a6f04850036e154f4f87e72e0509a8ff20a33cb` (`git show 4a6f048:PREREG.md`); the pre-translation project state is `02b66fc9d1797c3be77a4d9319a4143837bb8f5a`. Hypotheses, criteria, seeds, and all 14 hashes below are unchanged. The required G6 limitation is rendered in English. This post-freeze editorial deviation is disclosed in the final report.

> **Frozen on 2026-09-20 on the specification author's instruction** (decision D58, `docs/decisions.md`); the author accepted the full text at commit `2209e6a` (amendments D50–D57). After freezing, this file and the files listed in section 11 must remain unchanged; any departure must be reported as a deviation in the final report. The test split opens only when this file contains the `FROZEN` status line **and** every hash in section 11 matches its file on disk (`src/flight_or_bite/prereg.py`, SPEC §8); every access to `test` is logged in `runs/test_access.log`.
> Anything not specified here is labeled **exploratory** in the final report (SPEC §8). The `probe_looming`, `probe_jev`, `probe_interaction`, `probe_r5`, `grid_loss`, `env_sweep`, and `calibration` probes and the M3 gate run are not confirmatory; hypotheses H1–H5 are tested on **fresh seeds** not previously used.

## 1. What is compared

Arbiters in a food-versus-threat task (SPEC §2–§4, with deviations recorded in `docs/decisions.md`):

- **connectome** — LIF simulation of the FlyWire v783 connectome (Shiu et al. model, parameters in `configs/lif.yaml`), `event` backend; frozen encoding (D36): rate coding, sugar `R_max` 102.8 Hz, bitter 102.8 Hz, looming 2.34 Hz, `alpha` = 1.0; decoder: EAT — 4 MN9 spikes within 50 ms, ESCAPE — one spike from any DNp01; the first event wins, exact ties → ESCAPE, otherwise IDLE at 500 ms. Neuron sets: `data/circuits.yaml`. The backend was cross-checked against the Brian2 reference on conflict trials (10 trials, sugar 0.6 + looming 0.8, frozen encoding, identical input): 26,502 of 26,502 spikes matched, as did decisions and decision times in 10 of 10 trials (`reports/crosscheck_brian2.md`).
- **jev** — `typesafe/jev-1.13` through OpenRouter Decisions (a response outside this family aborts the run); one Choice question, identical across modes; four state modes in a 2 × 2 design: **rules package** absent/present × numeric/bucketed observations. The rules factor is a package: environment rules (in `instructions`, before the question) **together with** option descriptions in `criteria`; these are not varied independently, so their contributions are not separated. Templates in `configs/jev_prompts/`, version v1, approved by the author with amendments and not tuned on `dev`; full text in `reports/jev_templates.md`.
- **oracle**, **fixed_priority**, **random** — SPEC §4.4.
- Environment: `configs/env.yaml` (SPEC §3 with `p_food` 0.3, `eat_gain` 8, `escape_cost` 1).

Each arbiter uses its **native action** (D27): connectome — the outcome of one simulation; Jev — the `choice` field; oracle and fixed_priority — argmax; random — uniform choice.

## 2. Primary metric (RQ2)

Mean lifetime in trials (censored at 500), **online mode**, 300 paired episodes on test seeds 100000–100299, without a deadline. **The primary comparison is `connectome` versus `jev_informed`**: paired mean lifetime difference on identical seeds with a 95% bootstrap CI; this is the only comparison used to declare a winner. `oracle`, `fixed_priority`, and `random` play the same seeds and define the scale (`% of oracle`); their paired comparisons with the two main arbiters are reported descriptively. Jev participates online only in its **primary state mode**. Selection rule (specified by the author before the run): all four modes play the same **50 dev episodes (seeds 0–49)** online using native actions; select the mode with the highest mean lifetime, breaking ties by fewer calls. The selection result is in section 2a and is recorded in this file before access to `test`.

### 2a. Primary Jev mode: `informed`

Selected by the rule on dev seeds 0–49 (`reports/jev_mode_selection.md`): mean lifetime `informed` 64.26, `informed_bucketed` 64.20, `naive` 25.98, `bucketed` 16.82 trials. The difference between `informed` and `informed_bucketed` is not statistically significant (+0.06, CI includes zero); the rule was applied as written. For the primary metric on `test`, Jev participates only in `informed` mode. Main-run arbiters: `connectome`, `jev_informed`, `oracle`, `fixed_priority`, `random`. Expected Jev usage on `test`: approximately 300 episodes × ~65 trials ≈ 20,000 calls.

- Paired comparison on identical seeds; bootstrap over episodes, 10,000 resamples, 95% CI for the difference; declare a winner only if the CI excludes zero.
- `% of oracle = (L − L_random) / (L_oracle − L_random)`.
- Secondary analysis: the same procedure with actions sampled from `probs` (`sample_from_probs`, SPEC §7) — **100 paired episodes**, test seeds 100000–100099. Connectome, oracle, and `fixed_priority` have degenerate probabilities (one outcome has probability 1), so their results match native actions; Jev requires separate online calls (approximately 6,500).

### 2b. Jev failure policy

Never substitute a Jev decision with IDLE, a random action, or a cached response. HTTP 429 / 500 / 502 / 503 / 524 / 529 and transport errors receive up to 5 retries with delays of 2, 4, 8, 16, and 30 s; decisions requiring a retry are marked `retried` and excluded from latency statistics, but their actions are used. Exhausted retries, any other status (401, 402, 422, …), an invalid response body, or a response outside the `typesafe/jev-1.13` family **stop the run**; the incomplete episode is discarded in full and replayed from the beginning on the same seed after the cause is resolved; completed episodes are retained. Every stop, discarded episode, and retry count is reported. All exchanges, including failures, are saved in `runs/jev_raw/`. Report the run date and exact model ID returned; a dated snapshot change within the family during a run is reported but does not stop the run.

## 3. Confirmatory connectome hypotheses (RQ1)

Common to H1–H4: v783 connectome, `event` backend, full 500 ms trials, frozen encoding, looming ∈ {0.6, 0.8, 1.0}, **100 paired repetitions per level**, fresh trial seeds **9,000,000 + 1000·(hypothesis number) + 100·(level index) + repetition**. Each channel draws input from its own RNG stream (seed, channel), pairing conditions on the same seed. Holm correction is applied **across the three looming levels within each hypothesis**; significance level 0.05. Unless stated otherwise, hunger = 0 and bitter = 0.

| | Hypothesis | Outcome | Comparison | Test | Confirmed if |
|---|---|---|---|---|---|
| **H1** | Sugar 0.6 reduces the probability of a DNp01 spike | DNp01 emitted ≥ 1 spike: yes/no | sugar 0.6 + looming versus looming-only | exact two-sided McNemar test | minimum Holm-adjusted p < 0.05 and b > c at every level with discordant pairs (b means control yes, condition no) |
| **H2** | Suppression increases monotonically with sugar dose | same | sugar ∈ {0, 0.3, 0.6, 1.0} on the same seeds | permutation trend test: statistic T = Σ over seeds Σ over doses (dose rank · outcome); null distribution from 100,000 within-seed permutations of dose labels; one-sided (decreasing) | minimum Holm-adjusted p < 0.05 |
| **H3** | Ablating M_loom (25 neurons, `data/circuits.yaml`) removes the effect | d = (control − condition) without ablation − (control − condition) with ablation in both arms, by seed | sugar 0.6, identical seeds in all four cells | exact two-sided sign test on nonzero d | minimum Holm-adjusted p < 0.05 and Σd > 0; also report the retained effect fraction with a bootstrap CI |
| **H4** | Hunger strengthens food priority: hunger 1 versus hunger 0 at sugar 0.6 reduces P(ESCAPE) | primary: decoder chose ESCAPE: yes/no; **additional: DNp01 emitted ≥ 1 spike: yes/no** (same test, reported separately, excluded from the criterion) | hunger = 1 versus hunger = 0 (at `alpha` = 1, sugar GRN rates double) | exact two-sided McNemar test | as in H1, for the primary outcome |

Ablation means that a neuron cannot spike (`event` kernel, `ablated` parameter).

## 4. Planned H1 robustness analysis

Repeat H1 with one parameter changed at a time; protocol and test as in H1 (paired exact McNemar, **100 pairs per level** of looming ∈ {0.6, 0.8, 1.0}, Holm across levels), seeds 9,001,000 + 10,000·(variant number) + 100·(level index) + repetition. This analysis is **planned but not confirmatory**: H1 status is determined only by the primary run; here, report whether effect direction (b > c) and significance are retained.

| No. | Variant | Change |
|---|---|---|
| 1 | `r_max_sugar × 1.5` | Sugar `R_max` (and bitter, tied to it) 102.8 → 154.2 Hz |
| 2 | `r_max_looming × 1.5` | Looming `R_max` 2.34 → 3.52 Hz |
| 3 | `w_syn × 1.5` | Global model constant 0.275 → 0.4125 mV |
| 4 | `alpha` = 0.5 | At **hunger = 0.5** (`alpha` has no effect at hunger = 0); control and condition both use hunger 0.5 |
| 5 | `alpha` = 1.5 | Same |
| 6 | `theta_eat` = 3 spikes / 50 ms | Decoder only; the H1 outcome (DNp01 spiked) is independent of it, so this variant uses the outcome decoder chose ESCAPE |
| 7 | `theta_eat` = 5 spikes / 50 ms | Same |
| 8 | Population looming code | Level = fraction of LPLC2/LC4 stimulated at 100 Hz, `f_max` = 0.025390625 (`reports/probe_r5.md`, part D) |

The **×0.5** weakening variants (`r_max_sugar × 0.5`, `w_syn × 0.5`) are excluded from the H1 robustness analysis and reported as **“the network is silent”**: in G6 their signals do not reach the readout neurons (MN9 does not meet the EAT criterion; with `w_syn × 0.5`, neither MN9 nor DNp01 emits any spikes). There is no sign reversal: the effect has no activity on which to manifest.

## 5. Jev hypothesis (H5, RQ3)

**H5. Sugar shifts Jev's escape curve: direction and magnitude compared with the oracle.**
Slice: bitter = 0, hunger = 0.5, shared by all three arbiters (H1–H4 use hunger 0; here nonzero hunger is needed for `alpha` and the oracle's food value to contribute), looming = 0.0, 0.1, …, 1.0; sugar ∈ {0, 0.6}.
Quantity: Δ = mean across the 11 looming levels of [p_escape(sugar 0.6) − p_escape(sugar 0)].
- Jev (primary mode): `p_escape` is the `probabilities["ESCAPE"]` field, 20 repetitions per point (440 calls); CI for Δ_Jev from bootstrap over repetitions, 10,000 resamples.
- Oracle: `p_escape` ∈ {0, 1} (deterministic), Δ_oracle without a CI. **Computed before freezing: Δ_oracle = −0.0909 (−1/11), negative.** At sugar = 0, the oracle escapes starting at looming 0.4 (exact boundary 0.327); at sugar = 0.6, starting at 0.5 (boundary 0.413). At the other ten grid levels, sugar does not change its escape decision.
- Connectome: `p_escape` is the fraction of trials choosing ESCAPE, 40 trials per point, fresh seeds 9,005,000+; CI from bootstrap over trials.
Confirmatory claim: **Δ_Jev ≠ 0 (95% CI excludes zero)**; report the signs of Δ_Jev, Δ_oracle, and Δ_connectome, and differences Δ_Jev − Δ_oracle and Δ_connectome − Δ_oracle with CIs. The hypothesis is not directional: the sign is reported but is not part of the confirmation criterion.

## 6. Validity gates (SPEC §5) — M3 result

Protocol and thresholds: `configs/gates.yaml`, fixed in commit `921ffaf` before the run; results: `reports/gates.md`, `reports/gates/G*.json`. The author accepted M3 on 2026-09-20.

- **G1–G5 and G7 passed** (G1 ρ = 0.951; G2 reduction in `p_eat` 100%; G3 ρ = 0.995; G4 — signals do not reach output neurons in shuffled graphs, all three null metrics equal 0 in 20 of 20 graphs; G5 — three of three criteria; G7 — minimum Holm-adjusted p 0.0015).
- **G6 failed (9 of 11 variants passed).** Under SPEC §5, the final report must explicitly state: **“conclusions depend on manually chosen parameters.”** Both failed variants are ×0.5 weakening (`r_max_sugar × 0.5`, `w_syn × 0.5`); the network is silent, with no sign reversal. The other nine variants (`r_max_sugar × 1.5`, `r_max_looming` ×0.5 and ×1.5, `w_syn × 1.5`, `alpha` 0.5 and 1.5, thresholds of 3 and 5 spikes, population looming code) preserve direction and monotonicity.
- Gate thresholds were not changed after viewing results.

## 7. Psychometrics and calibration (RQ3, RQ4) — table mode

For RQ3/RQ4 only (D27). Bucketed modes query only unique level combinations (900 of the 1,225 points in grid B); other points receive copies. Grid B: 7 × 5 × 7 × 5 = 1,225 points, uniformly spaced on [0, 1] (`configs/grid.yaml`). Connectome: `N_rep` = 20. Jev: all four modes, `N_rep` = **10 in two passes of 5**, separated by **at least 12 hours**; each table row has a `session` column (1 or 2). Under D47 this requires (1,225 + 1,225 + 900 + 900) × 10 = 42,500 calls. The policy at a node is the mean across both passes; between-pass divergence (Jensen–Shannon divergence between session policies, by mode) is reported as a measure of service stability over time. Deviation from D2 (`N_rep` = 20): 20 repetitions would exceed `--max-calls`.
- RQ3: logistic fits to `p_escape(looming)` and `p_eat(bitter)` slices; threshold and slope for connectome, Jev, and oracle; mean Jensen–Shannon divergence over the grid.
- RQ4: Brier score and reliability table for Jev `p_escape` against the label “ESCAPE is optimal according to the oracle.”

## 8. Decision time (RQ5; SPEC §6 as amended by D10–D15)

- Measure client-side `t_wall` only (`perf_counter_ns`); additionally measure `t_sim` for the connectome. Report p50 / p95.
- Report Jev latency **separately for each state mode** (request lengths differ by tens of times because rules are included in `instructions`). Exclude calls retried after network errors (`retried` > 0) and copied responses in bucketed tables (`cache_hit`).
- Jev: sequential calls, one keep-alive session, `X-OpenRouter-Cache: false` header; the first 20 calls are warm-up, with the first cold call reported separately; states uniformly sampled over grid B.
- Connectome: one process, graph in memory (`t_load` reported separately), early stopping at the decoder event; RTF = `t_sim` / `t_wall`.
- Measurements used to make decisions are run by the human author in their own terminal, on AC power, under `caffeinate -i` (D5).
- **Chronometric hypothesis H6.**
  - **Primary test (connectome):** sugar delays the first DNp01 spike. Data: H1 pairs (sugar 0.6 + looming versus looming-only, identical seeds) in which DNp01 spikes **in both arms**; quantity: `t_sim` of the first DNp01 spike. Paired two-sided Wilcoxon test on differences (condition − control), separately at each looming level, with Holm correction across three levels. Confirmed if the minimum Holm-adjusted p < 0.05 and the median difference at that level is positive. Report pair counts and medians per level. No new simulations required.
  - **Secondary analysis (connectome):** association between `t_sim` and conflict difficulty d = 1 − |p_escape − p_eat| across grid B nodes. Exclude IDLE trials (their `t_sim` = 500 ms is censoring, not latency); include only nodes with p_eat + p_escape ≥ 0.5; Spearman ρ between d and median `t_sim` at each node, with a 95% bootstrap CI over nodes.
  - **Jev (primary mode), equivalence:** `t_wall` is independent of d if the 95% bootstrap CI for Spearman ρ between d and `t_wall` lies entirely within **[−0.1, 0.1]**. Data: uncached, non-retried calls from the primary-mode table. A CI extending beyond either boundary means equivalence has not been demonstrated.
- **Deadline sweep:** `deadline_ms` ∈ {1, 3, 10, 30, 100, 300, 1000, 3000}. Report the **fraction of decisions meeting the deadline** (latency ≤ `deadline_ms`) from measured decision-latency distributions in the main online run, per arbiter, in two tracks: `wall` (all use `t_wall`) and `native` (connectome uses `t_sim`, others use `t_wall`). Survival under deadlines is not simulated (deviation from SPEC §6.3-D).
- “Speed versus quality” figure: X — `t_wall` p50 (log scale), Y — % of oracle; show the connectome twice (`t_wall` and `t_sim`).

## 9. Secondary analyses (listed in advance)

Jev call budget (`--max-calls` limit = 100,000; 9,343 used at freezing, including a smoke test of the test command on 5 dev episodes): main run ≈ 20,000; secondary sampled run ≈ 6,500; tables 42,500; H5 440; latency benchmark across four modes ≈ 4,100 — approximately 83,000 in total.

Final energy; causes of death (starvation / predator / toxin / missed deadline); decision cost; outcomes when sampling from `probs`; the other three Jev modes in table mode. The “50 live episodes versus table” cross-check from SPEC §7 is **dropped**: after D27 the primary metric is already measured online, and table-mode losses have been measured separately (`reports/grid_loss.md`).

## 10. Questions not investigated and claims not to be made

- Which neuron in random sensory set 5 (`reports/probe_r5.md`, part A) causes DNp01 suppression.
- Through which targets M_loom neurons act (stimulated LPLC2/LC4, other DNp01 partners, or direct synapses).
- **cL20:** ablating it does not remove the effect (G5: 34 of 34 pairs retained). Its targets on this path, LC4 and LPLC2 (345 of 361 synapses onto looming-active DNp01 partners), are clamped sources in the model: each Poisson input forces a spike regardless of inhibition (verified: 17,916 LPLC2/LC4 spikes in 60 paired trials, no differing sugar/no-sugar pairs). This path is invisible by construction, and no claims are made about it. The model's mechanism is carried by the other 24 M_loom neurons: ablating them while retaining cL20 removes the effect completely (b − c: 34 → 0).
- Whether a subset of these 24 neurons is sufficient was not investigated.
- Behavior of shuffled graphs after recalibration (they were not recalibrated).
- Looming input is delivered directly to LPLC2/LC4, bypassing the retina; visual processing is not modeled. DNp01 is a descending neuron whose axon is incomplete in the FlyWire volume; the escape motor output is not modeled.
- Absolute model firing rates are not interpreted (the original model authors' caveat); `theta_eat` is a burst criterion chosen by the implementer (E9).

## 11. Hashes (SHA-256)

Repository commit when hashes were recomputed: `0124ea4d031f57981fd997396bbda55da39e4a4d`. `--unlock-test`, `fob confirm`, and `fob confirm-h5` compare this table with files on disk. `configs/confirm.yaml` specifies sections 3, 4, 5 and the primary H6 test (seeds, levels, pair counts, tests); `configs/timing.yaml` specifies the timing protocol and deadline set in section 8; `configs/grid.yaml` specifies grid B and the two Jev table passes in section 7.

| File | SHA-256 |
|---|---|
| `configs/calibration.yaml` | `944007ecbe8be17d27fc1bbe35b3ae850d83329605e44fc75d8a66af82087826` |
| `configs/confirm.yaml` | `75d6e1c3de00aae581ae38983eb75c54673ea0134c6333958ea15bb2062c3281` |
| `configs/data.yaml` | `667e547824348ed16df23aa13d40fc52483c39e1f24e69ef46c13d5408663b8a` |
| `configs/encoding.yaml` | `70e7790de8afd552c4db4e86fb0901b325c56fab9f56e086c0cd7c80610e5f74` |
| `configs/env.yaml` | `3345e7dd228ce49ed086fb8adfe971250eb201cba2dff24ea12c30674f92d03e` |
| `configs/gates.yaml` | `b20f045b6ea94a72e28bf0210271dd58a3bd80bb0f70db41cba096c490e0f23b` |
| `configs/grid.yaml` | `53be9d215be4f6177129c7f808dd75ffccad61611371c03f8ef217354f35305e` |
| `configs/jev_prompts/bucketed.yaml` | `66d4c17ab751e32a2ca695700f28ab23f1677bcbf743a5ebf216298688407f0e` |
| `configs/jev_prompts/informed.yaml` | `6eb536568b51b7645cfccac878b8acc333336db5003857b7abd083a2262cebdb` |
| `configs/jev_prompts/informed_bucketed.yaml` | `36166bffca8afe8eb092c997198147d34cf2b44461c4b2c1b70434085f4d2b74` |
| `configs/jev_prompts/naive.yaml` | `910c0642f29b36e6c0dec1c6610471b2456add7afe2ac01962f3caadf70781d8` |
| `configs/lif.yaml` | `fc5783e388d4a761bf59599c642c1f41df9a998f0e40cdedeaa07f685bd08525` |
| `configs/timing.yaml` | `b8dd4ca9a34438aa5ab094222c85ab05e8a261ce7f684e7214bcfafb902580c9` |
| `data/circuits.yaml` | `e3e7c551a5ace519afb5d1920e163ebf9fb35a0932a3d7851e1f6487acf53771` |
