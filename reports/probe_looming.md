# Looming-channel probe (exploratory)

Date: 2026-09-20. Decision D18: exploratory run, **not** G3/G7 gates or a milestone. Nothing was tuned: all parameters were already configured before the run (`R_max` = 200 Hz, `T_sim` = 500 ms, LIF parameters from `model.py`). Connectome v783, `event` backend, no early stopping (every trial runs the full 500 ms). Everything here is **exploratory** (SPEC §8).

Reproduction: `uv run python scripts/probe_looming.py`. Raw data: `runs/20260920T005025_probe-looming/probe.json`; conflict-slice trials: `reports/probe_looming_trials.csv` (220 rows).

## 1. Sources read

**Shiu et al., Nature 2024** (full text, open access; doi:10.1038/s41586-024-07763-9). Project-relevant findings:

- The paper covers feeding (sugar, water, bitter, Ir94e → MN9) and antennal grooming. **LPLC2, LC4, giant fiber, and DNp01 are not mentioned** (0 occurrences). The authors did not model or validate the looming circuit.
- They chose feeding because the entire circuit lies within the FlyWire volume, “in contrast to other sensorimotor circuits that require descending neurons, which are incomplete in the Flywire volume.” DNp01 is a descending neuron.
- `W_syn` = 0.275 mV is “the single free parameter of the model.” Selection method, verbatim: “We chose W syn such that activation of sugar GRNs at 100 Hz resulted in roughly 80% of maximal MN9 firing.” Robustness was tested at `W_syn` ± 30%.
- All neurons have baseline firing rate 0 Hz; consequence, verbatim: “inhibitory connections to an inactive neuron have no effect.” “Because of these assumptions, the absolute firing rates of the model are unlikely to be accurate. Rather, we prefer to interpret broad differences in firing rates between different conditions.”
- Neuron sign: GABA and glutamate are inhibitory; each neuron is entirely excitatory or inhibitory, based on the majority of presynaptic sites at cleft-score threshold 50. Dopamine, octopamine, and serotonin are treated as excitatory.
- Model: 127,400 neurons from v630; 30 simulations of 1,000 ms per experiment; “approximately 5 min per 1,000 ms trial per central processing unit thread.”
- Sugar GRN activation recruits 45 neurons at 10 Hz and 455 at 200 Hz out of 127,400.
- Weight-shuffle control (preserving the global weight distribution): MN9 activated in 100% of real-graph simulations and 1 of 100 shuffled simulations (sugar 100 Hz).
- Bitter: adding bitter GRN activity to sugar inhibits MN6 and MN9 (Fig. 3b); inhibition occurs at the premotor-neuron level.
- Sides: the authors stimulated the **left** hemisphere (“Because GRN reconstructions on the left hemisphere are more complete … we performed unilateral left hemisphere activation for all simulations, except for Extended Data Fig. 1d”) and read the **contralateral** MN9, which responds more strongly than the ipsilateral neuron.
- Omitted: gap junctions, non-spiking neurons, internal state, neuropeptides and neuromodulation, morphology, receptor dynamics. Overall accuracy across 164 tested predictions: 91% (84% excluding split-GAL4 screening).

**neuroai.science, “Are flies playing Beat Saber?”** (full text). Project-relevant facts and author claims:

- On the Shiu model: “only a few hundred neurons are actually activated in the simulation: they were not able to extend the simulation to meaningfully engage central, intrinsic neurons for non-stereotyped behaviors”; the global constant “was fit by trial and error.”
- The author's criterion for a functioning simulation is sensation connected to motor output “in a non-trivial and adaptive way.” A noise-driven recurrent network wired to buttons can produce apparently complex behavior without a sensorimotor loop (“random button mashing”).
- A flexible trainable readout or backpropagation through a connectome makes the connectome “beside the point” (example: a C. elegans connectome controlling a fly body).
- Quoting Kording et al. (2026): “without pre-specified, independently verifiable metrics, even technically interesting results attract legitimate skepticism.”
- Vision: a realistic visual-system model is hybrid, “with (mostly) graded inputs and spiking outputs”; a Shiu-style LIF network has no functional visual system.
- Missing from a connectome: synaptic strengths, delays, and intrinsic neuronal electrophysiology.

## 2. Identifiers

Source for LPLC2, LC4, DNp01, and the annotation-based bitter GRN set: `flyconnectome/flywire_annotations` @ `8587524c17`, file `supplemental_files/Supplemental_file1_neuron_annotations.tsv` (Schlegel et al. 2024), verified against Git blob SHA-1 `afea3e15a5…` and SHA-256 `9a4f8b2f84…`. Its README defines `root_id` as “the ID of the neuron in the FlyWire 783 release”; `side` is the soma side (nerve entry side for sensory neurons). Of 139,248 annotation rows, 138,625 root IDs occur in our `Completeness_783.csv`. Codex was not used. All sets are recorded in `data/circuits.yaml` with provenance.

| Set | Selection criterion | IDs | Sides (annotation table) | Present in v783 | Transmitter (`top_nt`) |
|---|---|---|---|---|---|
| LPLC2 | `cell_type == 'LPLC2'` | 210 | left 108, right 102 | 210 | acetylcholine: 210 |
| LC4 | `cell_type == 'LC4'` | 104 | left 54, right 50 | 104 | acetylcholine: 104 |
| DNp01 | `cell_type == 'DNp01'` | 2 | left 1, right 1 | 2 | left: acetylcholine; right: **glutamate** |
| Bitter GRNs (annotations) | `cell_sub_class == 'bitter'` | 65 | left 32, right 33 | 65 | acetylcholine 38, serotonin 27 |
| Bitter GRNs (model authors) | `figures.ipynb` @ `91bdd1e7dc`, `neu_bitter` (v630 IDs) | 21 | all 20 found: left | 20 (missing `720575940618600651`) | — |

Additional facts:

- **DNp01.** Left `720575940622838154`: 479 incoming edges (4,327 synapses), 285 outgoing. Right `720575940632499757`: 483 incoming (5,147 synapses), 242 outgoing. The annotation table labels the right neuron's `top_nt` as glutamate, but the authors' connectivity file (`Connectivity_783.parquet`) marks both DNp01 neurons `Excitatory` = 1.
- **Direct connections from stimulated neurons to readouts.** LPLC2+LC4 → DNp01: 293 edges from 293 of 314 neurons, 1,885 synapses, all excitatory. Sugar GRNs → MN9: 0 edges.
- **The bitter GRN set is not yet selected**; both are stored in `circuits.yaml`.
- **MN9.** No neuron is labeled cell type MN9 in the annotations. Our ID `720575940660219265` is `super_class` motor, `cell_sub_class` ingestion_motor_neuron, `cell_type` CB0701, right side. The authors' `figures.ipynb` uses `ids_mn9 = [720575940660219265, 720575940645521262] # left and right`; the second ID exists in v630 but **not in v783**.
- **Side labels in the authors' notebook and annotations are reversed.** The project's 20 sugar GRNs (“right hemisphere” in the notebook) have annotation `side` = left. The authors' `neu_sugar_left` list (10 IDs, 9 present in v783) is annotated right. MN9, called left by the authors, is annotated right. Under either convention, the project's MN9 is contralateral to its sugar GRNs. No explanation of reversed sides was found in the annotation repository README.
- The annotation table contains 129 `sugar/water` GRNs (122 type `LB3`); all 20 project sugar GRNs are `sugar/water`, `LB3`.

## 3. Looming → DNp01 dose-response curve

Input: Poisson stimulation of all 314 bilateral LPLC2+LC4 at `looming · 200 Hz` (SPEC §4.1), sugar = 0. 11 levels × 10 repetitions, seeds 5,000,000+. “DNp01 spiked” means at least one spike from either DNp01 within 500 ms; `t_sim` is the first such spike time.

| looming | Input, Hz (requested) | Input, Hz (observed) | P(DNp01 spike) | P by side: left / right | First spike t_sim p50, ms | Min–max, ms | DNp01 rate, Hz: left / right | P(MN9 spike) | Network spikes | Active neurons | s/trial |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 0 | 0.0 | 0.0 | 0.0 / 0.0 | — | — | 0.0 / 0.0 | 0.0 | 0 | 0 | 0.01 |
| 0.1 | 20 | 19.9 | 1.0 | 1.0 / 1.0 | 11.8 | 8.5–13.8 | 57.6 / 85.8 | 0.0 | 5,883 | 535 | 0.867 |
| 0.2 | 40 | 39.8 | 1.0 | 1.0 / 1.0 | 8.0 | 7.2–9.6 | 99.0 / 124.6 | 0.0 | 12,213 | 696 | 3.481 |
| 0.3 | 60 | 59.6 | 1.0 | 1.0 / 1.0 | 6.7 | 6.4–7.0 | 124.6 / 144.0 | 0.0 | 18,133 | 860 | 7.232 |
| 0.4 | 80 | 79.4 | 1.0 | 1.0 / 1.0 | 5.8 | 5.3–6.5 | 140.2 / 160.4 | 0.0 | 23,912 | 954 | 8.104 |
| 0.5 | 100 | 98.7 | 1.0 | 1.0 / 1.0 | 5.3 | 4.6–6.1 | 152.4 / 171.0 | 0.0 | 29,183 | 1,049 | 5.384 |
| 0.6 | 120 | 118.9 | 1.0 | 1.0 / 1.0 | 5.2 | 4.9–6.0 | 163.2 / 182.2 | 0.0 | 34,690 | 1,141 | 1.82 |
| 0.7 | 140 | 138.0 | 1.0 | 1.0 / 1.0 | 4.8 | 4.6–5.1 | 171.6 / 189.6 | 0.0 | 39,915 | 1,250 | 3.627 |
| 0.8 | 160 | 157.8 | 1.0 | 1.0 / 1.0 | 4.6 | 4.3–5.0 | 181.8 / 199.0 | 0.0 | 45,244 | 1,352 | 8.46 |
| 0.9 | 180 | 176.6 | 1.0 | 1.0 / 1.0 | 4.5 | 4.0–4.7 | 187.2 / 204.0 | 0.0 | 50,185 | 1,451 | 9.616 |
| 1.0 | 200 | 196.4 | 1.0 | 1.0 / 1.0 | 4.2 | 4.1–4.6 | 193.4 / 212.0 | 0.0 | 55,264 | 1,554 | 9.638 |

- No measurements between levels 0 and 0.1 (11-level grid as specified).
- The s/trial column is wall time on this machine during the run (overnight, without power/load controls); variation between neighboring levels (1.8–9.6 s) is not monotonic in spike count. For comparison, a 500 ms sugar trial in `reports/perf.md` takes 0.174 s.

## 4. Pathway overlap

An active neuron emits at least one spike in at least one of 10 trials of 500 ms. Seeds 6,000,000+. Set membership was not saved to disk, only the sizes and counts below.

**Level 1.0** (sugar-only: sugar = 1.0, looming = 0; looming-only: looming = 1.0, sugar = 0):

| Quantity | sugar-only | looming-only |
|---|---|---|
| Active neurons (spike in at least 1 of 10 trials) | 424 | 1,745 |
| Active in ≥ 5 of 10 trials | 368 | 1,532 |
| Active neurons excluding directly stimulated neurons | 404 | 1,431 |
| Includes MN9 | yes | no |
| Includes DNp01 | 0 of 2 | 2 of 2 |

Set intersection: **23** neurons (11 using the ≥ 5 of 10 criterion); union: 2,146.

| Synapses (sign = presynaptic neuron sign in connectivity file) | |
|---|---|
| sugar-active → DNp01 directly | 4 edges: excitatory 0 (0 synapses), inhibitory 4 (7); 3 sources, 2 targets |
| sugar-active → DNp01 inputs (862 presynaptic partners of DNp01; 3 sugar-active) | 787 edges: excitatory 188 (992 synapses), inhibitory 599 (3,859); 233 sources, 296 targets |
| looming-active → MN9 directly | 29 edges: excitatory 8 (10 synapses), inhibitory 21 (1,246); 29 sources, 1 target |
| looming-active → MN9 inputs (227 partners of MN9; 29 looming-active) | 5083 edges: excitatory 1968 (18,747 synapses), inhibitory 3115 (36,704); 644 sources, 220 targets |
| Reference: sugar-active → MN9 directly | 60 edges: excitatory 31 (1,582 synapses), inhibitory 29 (859); 60 sources, 1 target |
| Reference: looming-active → DNp01 directly | 469 edges: excitatory 385 (3,530 synapses), inhibitory 84 (2,162); 437 sources, 2 targets |

**Level 0.6** (sugar-only: sugar = 0.6, looming = 0; looming-only: looming = 0.6, sugar = 0):

| Quantity | sugar-only | looming-only |
|---|---|---|
| Active neurons (spike in at least 1 of 10 trials) | 385 | 1,309 |
| Active in ≥ 5 of 10 trials | 349 | 1,125 |
| Active neurons excluding directly stimulated neurons | 365 | 995 |
| Includes MN9 | yes | no |
| Includes DNp01 | 0 of 2 | 2 of 2 |

Set intersection: **12** neurons (8 using the ≥ 5 of 10 criterion); union: 1,682.

| Synapses (sign = presynaptic neuron sign in connectivity file) | |
|---|---|
| sugar-active → DNp01 directly | 4 edges: excitatory 0 (0 synapses), inhibitory 4 (7); 3 sources, 2 targets |
| sugar-active → DNp01 inputs (862 presynaptic partners of DNp01; 3 sugar-active) | 645 edges: excitatory 164 (899 synapses), inhibitory 481 (3,145); 207 sources, 235 targets |
| looming-active → MN9 directly | 26 edges: excitatory 8 (10 synapses), inhibitory 18 (1,155); 26 sources, 1 target |
| looming-active → MN9 inputs (227 partners of MN9; 26 looming-active) | 4239 edges: excitatory 1740 (17,516 synapses), inhibitory 2499 (30,198); 511 sources, 219 targets |
| Reference: sugar-active → MN9 directly | 61 edges: excitatory 32 (1,583 synapses), inhibitory 29 (859); 61 sources, 1 target |
| Reference: looming-active → DNp01 directly | 449 edges: excitatory 375 (3,458 synapses), inhibitory 74 (1,957); 419 sources, 2 targets |

## 5. Conflict slice: sugar = 0.6 × looming

20 repetitions per level, seeds 7,000,000+, full 500 ms. Per-trial data (first MN9, left/right DNp01 spike `t_sim`, rates, network activity) are in `reports/probe_looming_trials.csv`. Summary:

| looming | MN9 spiked | First MN9 spike t_sim, ms: p50 [min–max] | MN9 rate, Hz (mean) | DNp01 spiked | First DNp01 spike t_sim, ms: p50 [min–max] | DNp01 first | MN9 first | Neither | Active neurons |
|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 20/20 | 33.2 [29.8–50.7] | 69.5 | 0/20 | — | 0 | 20 | 0 | 342 |
| 0.1 | 20/20 | 37.3 [31.8–48.9] | 63.2 | 20/20 | 12.4 [9.5–15.6] | 20 | 0 | 0 | 851 |
| 0.2 | 20/20 | 38.3 [29.0–94.2] | 51.3 | 20/20 | 8.1 [7.4–9.4] | 20 | 0 | 0 | 989 |
| 0.3 | 20/20 | 41.4 [27.1–435.1] | 8.6 | 20/20 | 6.9 [6.0–7.6] | 20 | 0 | 0 | 1,075 |
| 0.4 | 17/20 | 41.2 [31.5–408.0] | 2.8 | 20/20 | 6.0 [5.2–6.9] | 20 | 0 | 0 | 1,130 |
| 0.5 | 5/20 | 33.9 [33.3–346.1] | 0.5 | 20/20 | 5.5 [4.8–6.7] | 20 | 0 | 0 | 1,209 |
| 0.6 | 5/20 | 34.5 [31.9–42.5] | 0.5 | 20/20 | 5.2 [4.5–5.8] | 20 | 0 | 0 | 1,293 |
| 0.7 | 3/20 | 34.4 [34.2–34.9] | 0.3 | 20/20 | 5.0 [4.4–5.4] | 20 | 0 | 0 | 1,400 |
| 0.8 | 4/20 | 38.2 [31.3–40.3] | 0.4 | 20/20 | 4.7 [4.4–5.1] | 20 | 0 | 0 | 1,482 |
| 0.9 | 0/20 | — | 0.0 | 20/20 | 4.5 [4.3–4.8] | 20 | 0 | 0 | 1,583 |
| 1.0 | 0/20 | — | 0.0 | 20/20 | 4.3 [4.1–4.6] | 20 | 0 | 0 | 1,673 |

For comparison, the same quantities without conflict (section 3 and `reports/status.md` §1.2): at sugar = 0.6 and looming = 0, MN9 fires at 69.5 Hz in this run; first DNp01 spike `t_sim` with looming-only is 11.8 ms (looming 0.1), 5.3 ms (0.5), 4.2 ms (1.0).

## 6. Measurement summary (without design conclusions)

1. With SPEC §4.1 looming encoding and `R_max` = 200 Hz, DNp01 spikes in 10 of 10 trials at every nonzero grid level starting at looming = 0.1; first-spike `t_sim` falls from 11.8 to 4.2 ms. The 11-level grid shows no intermediate probabilities between 0 and 1.
2. With looming-only, MN9 never spikes in 110 trials; with sugar-only, DNp01 never spikes in 20 trials (looming = 0 in the conflict slice).
3. DNp01 is first in all 200 conflict trials with looming ≥ 0.1. First DNp01 spike `t_sim` differs by tenths of a millisecond with versus without conflict (12.4 versus 11.8 ms at looming 0.1; 4.3 versus 4.2 ms at 1.0).
4. MN9 rate at sugar = 0.6 falls as looming rises: 69.5 → 63.2 → 51.3 → 8.6 → 2.8 → 0.5 Hz (looming 0 … 0.5), then 0.0 Hz at 0.9–1.0. Trials with MN9 spikes: 20/20 through looming 0.3, 17/20 at 0.4, 5/20 at 0.5, 0/20 at 0.9–1.0.
5. Direct connections from looming-active neurons to MN9 at level 1.0: 21 inhibitory edges (1,246 synapses), 8 excitatory edges (10). From sugar-active neurons to DNp01: 4 inhibitory edges (7 synapses), none excitatory.
6. Active sets overlap in 23 neurons at level 1.0 and 12 at level 0.6.
7. Looming recruits more network activity than sugar: up to 1,554 active neurons and 55,000 spikes per trial, versus 379 neurons and 8,000 spikes.

## 7. Not included in this probe

- Looming levels between 0 and 0.1; other `R_max` values; LPLC2-only or LC4-only input; unilateral stimulation.
- The SPEC §4.1 decoder (`theta_eat`, sliding window); raw at-least-one-spike outcomes and first-spike times are reported instead of `p_eat`/`p_escape`.
- Hunger (`alpha` unset), bitter input, shuffled graphs, ablations, independent race model (G7).
- Brian2 cross-check for looming trials (backend checked on sugar input and a random graph).
- Identities of the 23 shared neurons.
