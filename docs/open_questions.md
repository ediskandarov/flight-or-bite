# Questions for the human author

> Historical M1–M3 question log, not the current blocker list. Templates v1
> were approved (D46), preregistration frozen (D58), and G6 accepted as a failure (D41).
> Current status: [handoff.md](handoff.md) and [decisions.md](decisions.md).
> As of 2026-10-06, all three author-run experiments under D59 are complete.
> The [run instructions](../reports/run_instructions.md) are retained for reference.

Format under SPEC §12: blocker → options → recommendation and rationale.
Historical entries updated: 2026-09-20 (overnight), after M2 and the probes.

## Resolved

- **Jev access** — through OpenRouter Decisions (`jev_api_notes.md` §1a, §11).
- **End-of-M0 questions (Q1–Q10)** — all recommendations accepted on 2026-09-19; see `decisions.md` D1–D9.
- **Section 6 simplified** on 2026-09-20 (D10–D15): only `t_wall` (+ connectome `t_sim`), OpenRouter as
  the sole route, model `jev-1.13`, p50/p95. Removed: `t_server`/`t_gateway`, connection
  breakdown, concurrent-request testing, network metadata, and direct TypeSafe API access.

## Awaiting the author before M4 (2026-09-20)

1. **Approve Jev template wording** — `reports/jev_templates.md` (five wording questions at the end). M4 does not start before approval (D45). After approval, repeat the Jev probe with the new environment values and fourth mode (approximately 440 calls).
2. **“DECIDE” markers in `PREREG.md`:** primary Jev mode selection rule; paired repetition count for H1–H4; shared hunger and H5 directionality; Jev table size; whether to retain the “50 live episodes” cross-check.
3. **For information:** conflict-trial Brian2 cross-check — 26,502 of 26,502 spikes and 10 of 10 decisions matched (`reports/crosscheck_brian2.md`). It exposed decoder fragility from comparing intervals in floating-point milliseconds; the decoder now uses integer steps (E13). M3 gates predate this fix; “DNp01 spiked” outcomes are unaffected. Rerunning gates after the fix is the author's decision (approximately 1.5 hours).

## End of M3 (2026-09-20): gates and draft preregistration

Reports: `reports/gates.md`, `PREREG.draft.md`. Author decisions needed:

- **M3-1. G6 failed (9 of 11 passed).** Failures: `r_max_sugar × 0.5` (MN9 never meets EAT at any sugar level: maximum 11.8 Hz, ρ = 0.74) and `w_syn × 0.5` (network silent: no MN9 or DNp01 spikes). The other nine variants, including ±50% looming `R_max`, `w_syn × 1.5`, `alpha` 0.5/1.5, thresholds of 3 and 5 spikes, and population looming coding, preserve direction and monotonicity. SPEC §5 does not require stopping: report “conclusions depend on manually chosen parameters.” Accept as is or narrow G6's range (e.g. ±30%, as the original model authors used for `W_syn`)? The latter would change a threshold after viewing the result.
- **M3-2. cL20 alone is not required for the effect:** ablating it retains 100% of suppression (the same 34 pairs); ablating all 25 M_loom neurons removes the effect completely (0 of 34).
- **M3-3. “DECIDE” markers in `PREREG.draft.md`:** primary Jev mode selection on dev; paired repetition count for H1–H4 (40 or more); shared hunger and directional wording for H5; Jev table size (98,000 calls at 4 modes × N_rep 20 exhausts `--max-calls`); whether the “50 live episodes versus table” cross-check is needed after D27.
- **M3-4. Shuffled graphs take approximately 10 times longer than the real graph** (unstructured input spreads across the brain, enlarging the kernel's active set): G4 took about an hour with 5 processes. This is manageable for M4 (`shuffled` table: 2,000 simulations).

## Morning of 2026-09-20: implementing author decisions D25–D30 (stop after items 2 and 4)

Reports: `reports/calibration.md`, `reports/probe_interaction.md`, `reports/env_sweep.md`. Decisions needed:

- **R1. Environment.** None of the four requested configurations produces 25–75% oracle starvation deaths (observed 9–18%); the oracle's lead over `fixed_priority` falls to 7–17% (M2 acceptance threshold: 10%). In the reference table, `p_food` 0.2 (G 8 or 10), and `escape_cost` 1 with `p_food` 0.3 and G 8 meet the range. No configuration selected. Update numbers in `informed` after selection.
- **R2. “MN9 saturation” has no plateau** in the tested series through 3200 Hz (+7% at the final doubling); `theta_eat` = 74.8 Hz comes from the series maximum. In a 50 ms window this means 4 spikes (effectively 80 Hz).
- **R3. `alpha` is unset** — hunger does not affect encoding, and calibration excluded it.
- **R4. Bitter GRN set** has not been chosen (65 from FlyWire annotations, bilateral, or 20 from the model authors' list, unilateral); bitter `R_max` equals sugar `R_max` under D25.
- **R5. Interaction changed sign after calibration.** Looming no longer suppresses MN9 (27–31 Hz at all looming levels), but sugar reduces DNp01 responses: 104/120 trials without sugar versus 70/120 at sugar 0.6 (looming ≥ 0.5, same seeds; Fisher p ≈ 1e-6, test selected post hoc). Observed decisions differ from the independent race: at looming 1.0 the race predicts ESCAPE 72%, versus 35% observed.
- **R6. Shuffled graphs are silent:** MN9 responds in 0 of 4,400 trials, DNp01 in 5 of 4,400. They were not recalibrated.
- **R7. Tie rule** (EAT and ESCAPE in the same step → ESCAPE) was chosen by the implementer (E10); no ties so far.

## 0. Night of 2026-09-20: work under “proceed, I trust your judgement” and decisions still needed

Completed: looming probe (`reports/probe_looming.md`), M2 (`reports/eval_dev.md`), draft Jev templates and their probe (`reports/probe_jev.md`), policy-table infrastructure, and grid-loss measurements (`reports/grid_loss.md`). Deliberately **not** done: choosing `R_max`, `theta_eat`, `alpha`, or looming encoding; building Jev and connectome tables.

### N1. The looming channel saturates under the specified encoding
- **Facts** (`reports/probe_looming.md`): stimulating all 314 LPLC2+LC4 at `looming · 200 Hz` makes DNp01 spike in 100% of trials at every nonzero grid level starting at 0.1; first spike at 4–12 ms. In the conflict slice DNp01 wins in 200 of 200 trials. By comparison, Jev `p_escape` rises smoothly from ~0 to ~0.75 on the same slice; the oracle boundary lies between looming 0.3 and 0.4.
- **Design implication:** a first-threshold-crossing decoder makes the connectome choose ESCAPE at almost any nonzero looming. The environment produces looming ≥ 0.1 in 75% of trials (from SPEC §3 distributions: 0.8 · P(N(0.2, 0.2) ≥ 0.1) + 0.2 · P(N(0.7, 0.2) ≥ 0.1)).
- **Possible changes (author decision; none selected):** separate looming and sugar `R_max`; fraction of stimulated LPLC2/LC4; unilateral stimulation; rate-based rather than first-spike DNp01 decoding; nonlinear looming-to-rate mapping. Each is a manual assumption for `ENGINEERED.md` and a G6 candidate.
- **Recommendation:** choose and record a rule before running (e.g. “looming `R_max` is the rate giving P(DNp01 spike) = 0.5 at looming = 0.45, the environment's equal-likelihood point”). This calibrates to an environment property rather than the Jev comparison. The author must approve the rule itself.

### N2. Pathways interact in the wiring (relevant to RQ1)
- **Facts:** at sugar = 0.6, MN9 firing falls as looming rises: 69.5 → 8.6 Hz (looming 0.3) → 0 (0.9–1.0). Looming-active neurons send 21 inhibitory edges (1,246 synapses) to MN9. In the reverse direction (sugar-active → DNp01): 4 inhibitory edges, 7 synapses. Active sets overlap in 23 neurons.
- Exploratory, not G7: no independent race model was built.

### N3. Table mode loses much of sharp policies' survival
- **Facts** (`reports/grid_loss.md`): the oracle played from the specified 225-point grid retains 40% of its survival (60.1 versus 151.2), below direct `fixed_priority` (75.3). A 5,670-point grid retains 94%; 20,910 points retain 96%. Cause: interpolation of one-hot probabilities plus sampling.
- **Why it matters:** the primary metric (SPEC §7) is computed in table mode. With current encoding, connectome has a sharp policy and Jev a smooth one; different grid losses would distort their comparison.
- **Options:** (a) environment-aligned grid with a dense looming axis (G: 5,670 points; Jev ~19 hours sequentially, connectome ~113,000 simulations); (b) nearest-node probabilities rather than linear interpolation (deviation from SPEC §4.5; unmeasured); (c) online primary evaluation for a subset of episodes; (d) retain the design and report grid losses as a correction.
- **Recommendation:** (a) for sugar/bitter axes (free: 6 and 5 nodes), then measure loss for a **smooth** policy before choosing looming resolution; deterministic-policy losses overstate those expected for Jev.

### N3a. Grid loss depends on policy sharpness; smoothness itself is costly
- **Facts** (`reports/grid_loss.md`, “soft oracle” P ∝ exp(Q/τ)): on the specified grid a sharp policy retains 37% of survival, a smooth policy with a Jev-like `p_escape` curve retains 91%. The current table design penalizes a sharp connectome much more than a smooth Jev.
- **Separate finding:** played directly, the same gently sloped soft oracle survives 22.6 trials versus 145.7 for the sharp oracle and 14.1 for `random`. In this environment, SPEC §4's requirement to sample actions from probs penalizes any uncertain policy, even one built on optimal values.
- **Question for the author:** keep sampling primary and argmax secondary (SPEC §7), or reverse them? Nothing changed.

### N4. Jev templates — draft v0, written before observing responses
Three templates in `configs/jev_prompts/` were committed before the first call (`713fe97`). `bucketed` = `naive` with numbers replaced by 5 equal-width levels, without environment rules. Questions: is `informed` wording acceptable; add a fourth informed + bucketed mode; retain 5 equal-width levels?

### N5. M2 specification interpretations (V1–V8 in `ENGINEERED.md`)
Main points: only food can be toxic (V1); the oracle uses a stationary policy because the arbiter interface has no trial number (V2). Even the oracle dies to predators in 93% of episodes and survives an average of 151 out of 500 trials, a consequence of SPEC §3 environment parameters.

## A. End of M1 — a decision is needed before M2

### Q1. LIF backend
- **Facts** (`reports/perf.md`, 500 ms trial, v783): `event` 0.174 s (RTF 2.88); `brian2` 1.355 s
  (0.37); `torch-cpu` 2.147 s (0.23); `torch-mps` 4.627 s (0.11). With identical input, `event` matches
  Brian2 bit for bit (12,804 of 12,804 whole-network spikes); `torch-mps` differs
  (2 of 12,805) due to float32. With early stopping, an `event` decision costs approximately 2 ms.
- **Recommendation:** `event`. Keep Brian2 as the test reference. Retain PyTorch backends in
  the repository as measured and rejected candidates, without further development.
- **Author action:** under D5, rerun `uv run fob perf` in your terminal **on AC power** under
  `caffeinate -i`; my measurement used battery power. Ranking is unlikely to change (8× gap), but
  reportable absolute `t_wall` values must come from your run.

### Q2. Grid size
- **Facts:** connectome is no longer the bottleneck; the default grid takes ~2 minutes on 6 cores.
  Sequential Jev latency is the bottleneck (~0.4 s per call, 3 state modes).
- **Options:** A) 5×3×5×3 = 225 points (specification): Jev 13,500 calls, ~1.5 h; B) 7×5×7×5 = 1,225:
  Jev 36,750 calls (N_rep 10), ~4.1 h; C) 9×5×9×5 = 2,025: ~6.8 h.
- **Recommendation:** B, subject to final approval after M3 when the cost of looming trials is known
  (they will excite much more of the network). Denser sugar and
  looming axes matter most for RQ3 and interpolation error. Note MN9 response shape (Q4): with
  a uniform sugar axis, almost all information lies between 0.2 and 0.5.

### Q3. Connectome version and missing sugar GRN
- **Facts:** the paper used **630**; the public version is **783** (authors' `Readme.md`). G1
  passes on both (ρ 0.944–0.966). Version 783 lacks ID `720575940620900446`, one of the example's 21 sugar
  GRNs; currently 20 are stimulated on v783. Recorded in `data/circuits.yaml`.
- **Options:** (a) v783 and locate the successor ID in Codex/FlyWire; (b) v783 with 20 GRNs as is;
  (c) return to v630.
- **Recommendation:** (a). Other sets (bitter GRNs, LPLC2, LC4, DNp01) must be obtained at M3
  from Codex annotations, which are published for v783. Search primary sources for the successor
  at M3; if absent, use (b) and document it in `ENGINEERED.md`. Do not guess IDs.

### Q4. `R_max` and the narrow operating range of the sugar axis (information; decision at M3)
At temporary `R_max` = 200 Hz (E1), MN9 has a sigmoid response: silence below sugar 0.2, steep growth at
0.2–0.4, saturation around 90 Hz. `theta_eat` and `R_max` place the decision boundary on the sugar axis
and are the project's most influential manual parameters. At M3, choose them using a rule recorded
in advance (e.g. “EAT boundary at sugar = 0.5 without conflict”), rather than by eye.

### Q5. M1 commit
M1 changes are uncommitted. Commit them?

## B. Before preregistration (carried forward; decisions made, execution to verify)

- D2: `N_rep = 20` for Jev, cache retains repetitions. D7: third mode `bucketed`. D8: shared call
  counter. Due at M4. (D9 implemented and clarified by D13; D3 superseded by D11.)

## C. Required reading not yet completed

- Shiu et al. (Nature 2024): so far, implementation is based on the authors' code; read before M3 together with
  the neuroai.science methodology article (required before M3 by SPEC §13).
