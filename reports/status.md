# Status report for the specification author

Date: 2026-09-20. Repository `flight-or-bite`. Facts and numbers only; no interpretations or fixes.

> **Historical snapshot from the morning of 2026-09-20, not current status.** Later additions: `reports/probe_looming.md` (looming-circuit IDs, dose curve, conflict slice; fills the gaps in §1.3 and §2), `reports/eval_dev.md` (environment and oracle; fills §5), `reports/probe_jev.md` (exact requests and `p_escape` slice; fills §3), and `reports/grid_loss.md`. All planned experiments are now complete; see [final report](final_report.md) and [current README](../README.md).
“No data” means the corresponding code or measurement did not exist at this snapshot.

## 0. Milestone at the time of this snapshot

- M0 committed (`2d29c62`).
- M1 acceptance criteria met (G1 passed; `reports/perf.md` recommends backend and grid). SPEC §11 requires stopping after M1 for human confirmation; not yet received. M1 changes and the section 6 simplification are **uncommitted** (43 modified/new paths in `git status`, including this report).
- M2–M5 not started.
- Tests: 81, all passing. `SPEC.md` unchanged (30,579 bytes, matching the original at this snapshot).

## 1. Gates

| Gate | Status | Metric |
|---|---|---|
| G1 sugar → MN9 | **passed** | Minimum ρ across 4 runs = 0.944, threshold 0.8 |
| G2 bitter suppresses sugar | No data: not implemented; bitter GRN IDs not obtained | — |
| G3 looming → DNp01 | No data: not implemented; LPLC2, LC4, DNp01 IDs not obtained | — |
| G4 real versus shuffled | No data: graph shuffling not implemented | — |
| G5 ablation | No data: gates not implemented (backend neuron silencing exists and is tested on a toy graph) | — |
| G6 robustness | No data | — |
| G7 conflict | No data | — |

### 1.1 G1 gate run (`reports/gates/G1.json`)

Protocol: 11 sugar levels × 10 repetitions, 500 ms window, GRN input rate = sugar · 200 Hz, no hunger; metric: Spearman ρ across all 110 trials (MN9 firing over the full window). Seeds 2,000,000+.

| Run (backend/version) | Sugar GRNs | ρ across trials | ρ across level means | Means strictly increasing | Gate |
|---|---|---|---|---|---|
| event/v630 | 21 | 0.944 | 0.991 | no | passed |
| brian2/v630 | 21 | 0.955 | 0.980 | no | passed |
| event/v783 | 20 | 0.966 | 0.998 | no | passed |
| brian2/v783 | 20 | 0.960 | 0.998 | no | passed |

MN9 firing, Hz, by sugar level:

| sugar | event/v630: mean (SD) | brian2/v630: mean (SD) | event/v783: mean (SD) | brian2/v783: mean (SD) |
|---|---|---|---|---|
| 0.0 | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) |
| 0.1 | 0.2 (0.6) | 0.0 (0.0) | 0.0 (0.0) | 0.0 (0.0) |
| 0.2 | 3.2 (2.9) | 3.8 (3.6) | 1.8 (2.4) | 3.8 (4.1) |
| 0.3 | 32.0 (7.4) | 31.4 (8.1) | 29.0 (10.7) | 28.2 (8.7) |
| 0.4 | 60.0 (6.6) | 54.4 (7.4) | 50.6 (5.1) | 49.4 (11.1) |
| 0.5 | 68.4 (7.4) | 70.4 (6.4) | 61.0 (4.8) | 60.4 (6.9) |
| 0.6 | 75.6 (12.6) | 69.0 (5.8) | 66.6 (7.2) | 69.2 (5.5) |
| 0.7 | 81.8 (5.1) | 84.2 (8.0) | 73.6 (4.9) | 69.4 (5.4) |
| 0.8 | 83.4 (7.0) | 85.0 (5.9) | 80.4 (6.4) | 78.6 (3.1) |
| 0.9 | 92.4 (4.8) | 90.0 (6.5) | 83.4 (5.9) | 79.6 (7.5) |
| 1.0 | 91.4 (8.3) | 89.2 (4.1) | 87.2 (5.2) | 90.4 (5.9) |

### 1.2 Raw sugar → MN9 dose curve (separate run for this report)

`event` backend, same 11 × 10 design, 500 ms window, seeds 4,000,000+; raw data: `runs/20260920T002733_status-dose/dose.json`.
The EAT decoder does not exist (`theta_eat` unset), so SPEC §4.1 `p_eat` **was not computed**. Two raw quantities are reported instead: fraction of trials with at least one MN9 spike in the window, and simulated first-spike time.

**Connectome v783 (20 sugar GRNs, 138,639 neurons):**

| sugar | GRN input, Hz (requested) | GRN, Hz (observed) | MN9, Hz: mean (SD) | P(≥1 MN9 spike in 500 ms) | First MN9 spike t_sim, ms: p50 [min–max] | Network spikes | Active neurons |
|---|---|---|---|---|---|---|---|
| 0.0 | 0.0 | 0.0 | 0.0 (0.0) | 0.0 | — | 0.0 | 0.0 |
| 0.1 | 20.0 | 19.4 | 0.0 (0.0) | 0.0 | — | 268.4 | 40.1 |
| 0.2 | 40.0 | 39.5 | 3.0 (2.41) | 0.7 | 304.4 [67.6–453.4] | 789.3 | 95.4 |
| 0.3 | 60.0 | 58.6 | 23.0 (6.77) | 1.0 | 99.0 [56.6–150.6] | 1985.0 | 249.3 |
| 0.4 | 80.0 | 79.2 | 52.8 (6.71) | 1.0 | 54.4 [31.3–74.6] | 3482.5 | 312.5 |
| 0.5 | 100.0 | 99.4 | 60.8 (5.6) | 1.0 | 35.7 [31.4–71.4] | 4405.8 | 329.9 |
| 0.6 | 120.0 | 118.8 | 65.8 (6.84) | 1.0 | 35.5 [32.1–41.3] | 5082.4 | 338.7 |
| 0.7 | 140.0 | 138.3 | 78.6 (5.59) | 1.0 | 32.6 [29.7–46.7] | 6150.4 | 351.5 |
| 0.8 | 160.0 | 159.1 | 78.8 (6.27) | 1.0 | 29.9 [26.6–42.0] | 6745.1 | 358.9 |
| 0.9 | 180.0 | 179.2 | 82.6 (6.39) | 1.0 | 29.2 [26.0–32.6] | 7380.9 | 365.1 |
| 1.0 | 200.0 | 197.8 | 87.8 (4.24) | 1.0 | 26.2 [23.5–30.3] | 8067.0 | 379.0 |

**Connectome v630 (21 sugar GRNs, 127,400 neurons):**

| sugar | GRN input, Hz (requested) | GRN, Hz (observed) | MN9, Hz: mean (SD) | P(≥1 MN9 spike in 500 ms) | First MN9 spike t_sim, ms: p50 [min–max] | Network spikes | Active neurons |
|---|---|---|---|---|---|---|---|
| 0.0 | 0.0 | 0.0 | 0.0 (0.0) | 0.0 | — | 0.0 | 0.0 |
| 0.1 | 20.0 | 19.4 | 0.0 (0.0) | 0.0 | — | 292.8 | 38.9 |
| 0.2 | 40.0 | 39.5 | 8.2 (6.72) | 0.8 | 179.7 [104.4–319.2] | 939.9 | 131.4 |
| 0.3 | 60.0 | 58.6 | 32.8 (5.38) | 1.0 | 79.4 [48.5–125.6] | 2274.1 | 272.5 |
| 0.4 | 80.0 | 79.2 | 57.2 (5.81) | 1.0 | 44.6 [34.0–117.5] | 3797.2 | 320.5 |
| 0.5 | 100.0 | 99.2 | 68.6 (4.57) | 1.0 | 33.4 [29.8–62.5] | 4796.4 | 344.1 |
| 0.6 | 120.0 | 118.7 | 71.8 (6.1) | 1.0 | 34.2 [31.6–39.2] | 5531.8 | 351.1 |
| 0.7 | 140.0 | 138.5 | 80.6 (6.39) | 1.0 | 30.6 [26.2–36.0] | 6356.5 | 357.7 |
| 0.8 | 160.0 | 159.0 | 82.8 (4.31) | 1.0 | 31.1 [26.3–37.4] | 7168.8 | 369.1 |
| 0.9 | 180.0 | 179.4 | 88.2 (8.65) | 1.0 | 27.7 [25.1–30.8] | 7846.8 | 373.7 |
| 1.0 | 200.0 | 197.6 | 91.8 (7.87) | 1.0 | 25.5 [24.0–29.7] | 8484.0 | 385.2 |

Silence and saturation in numbers:
- sugar = 0: zero network spikes and active neurons (both versions).
- sugar = 0.1 (20 Hz): MN9 0.0 Hz in all 10 repetitions (both versions); mean network spikes per trial 268.4 (v783) / 292.8 (v630); mean active neurons 40.1 (v783, including 20 stimulated GRNs) / 38.9 (v630, including 21 stimulated GRNs).
- sugar = 0.2 (40 Hz): MN9 spiked in 7 of 10 (v783) and 8 of 10 (v630) trials.
- sugar ≥ 0.3: MN9 spikes in all 10 trials.
- MN9 rate increase per sugar step of 0.1: over 0.2→0.4, +20.0 and +29.8 Hz (v783), +24.6 and +24.4 Hz (v630); over 0.8→1.0, +3.8 and +5.2 Hz (v783), +5.4 and +3.6 Hz (v630). Maximum at sugar = 1.0: 87.8 Hz (v783), 91.8 Hz (v630).
- Active neurons at sugar = 1.0: 379 of 138,639 (v783), 385 of 127,400 (v630). Separate v630 count at 150 Hz for 1 s: 370 spiking neurons; 11,178 neurons received at least one synaptic input (8.8%).
- First MN9 spike t_sim (p50): 304 ms at sugar 0.2 → 26 ms at sugar 1.0 (v783); 180 ms → 25.5 ms (v630).

### 1.3 Looming → DNp01 dose curve

No data. LPLC2, LC4, and DNp01 IDs were not obtained from primary sources; looming encoding and ESCAPE decoding were not implemented. No looming-input simulation had been run.

## 2. Neuron groups (`data/circuits.yaml`)

| Group | IDs | Source | Brain sides |
|---|---|---|---|
| Sugar GRNs | 21 (v630); 20 (v783) | `philshiu/Drosophila_brain_model` @ `91bdd1e7dc`, `example.ipynb`, variable `neu_sugar` | Right hemisphere only, according to notebook wording: “some sugar-sensing neurons in the right hemisphere” |
| MN9 | 1 (`720575940660219265`) | Same notebook, `id_mn9 = 720575940660219265  #id for MN9` | One neuron; side not specified in source or independently checked |
| Bitter GRNs | 0 | Not obtained | — |
| LPLC2 | 0 | Not obtained | — |
| LC4 | 0 | Not obtained | — |
| DNp01 | 0 | Not obtained | — |

Codex/FlyWire had not been used as an annotation source; only site availability was checked (HTTP 200). All IDs came from the authors' code. Shiu et al. (Nature 2024) had not been read.

Connectome versions (files from the same repository, verified against Git blob SHA-1 at commit `91bdd1e7dc`):

| | v630 («which the paper used») | v783 («public version») |
|---|---|---|
| Neurons | 127 400 | 138 639 |
| Edges | 14 687 178 | 15 091 983 |
| Excitatory edge fraction | 59.9% | 60.0% |
| Edge weight (signed synapse count), min / max | −2358 / 1801 | −2405 / 1897 |
| Sugar GRNs found from list | 21 of 21 | 20 of 21 |
| MN9 incoming / outgoing edges | 229 / 83 | 227 / 82 |
| Sugar GRN out-degree, min / median / max | 51 / 72 / 98 | 51 / 70 / 98 |

**Missing sugar neuron.** ID `720575940620900446` occurs in `2023_03_23_completeness_630_final.csv` but not `Completeness_783.csv`. A successor ID in v783 **was not sought**. It is marked `absent_in: {783: [...]}` in `data/circuits.yaml`; v783 runs (G1, perf, dose curve) use 20 GRNs. Any other missing ID raises an error. `configs/lif.yaml` currently specifies `connectome_version: 783`.

## 3. Jev

**Model slug.** Requested `typesafe/jev-1.13`; all 26 live calls returned `typesafe/jev-1.13-20260917`, provider TypeSafe. Endpoint: `POST https://openrouter.ai/api/alpha/decisions` (alpha), key `OPENROUTER_API_KEY`, header `X-OpenRouter-Cache: false`. A model outside the `typesafe/jev-1.13` family aborts the run.

**Exact naive / informed / bucketed requests.** Not yet defined. `configs/jev_prompts/` contains only `.gitkeep`; `JevArbiter` and bucket boundaries are not implemented.

The only request sent to Jev (smoke test, none of the three modes), verbatim body:

```json
{"model":"typesafe/jev-1.13","questions":{"action":{"criteria":{"EAT":null,"ESCAPE":null,"IDLE":null},"instructions":"Which action should the agent take?","type":"choice"}},"state":{"bitter":0.05,"hunger":0.5,"looming":0.6,"sugar":0.7}}
```

**p_escape slice over looming.** No data: Jev was queried at only one state.

**Probability SD across repetitions at 3 points.** Data exist for **one** point only (state above): 20 byte-identical sequential requests on 2026-09-19. Values taken from `fob jev smoke` terminal output; raw responses were not saved.

| Option | Mean | SD | Min | Max |
|---|---|---|---|---|
| EAT | 0.5625 | 0.031 | 0.52 | 0.62 |
| ESCAPE | 0.4175 | 0.031 | 0.36 | 0.46 |
| IDLE | 0.0200 | 0.000 | 0.02 | 0.02 |

11 distinct probability vectors across 20 responses. argmax = EAT in all 20. An earlier single call with the same body via `curl` returned EAT 0.40 / ESCAPE 0.58 / IDLE 0.02, argmax = ESCAPE. A second run (2026-09-20, 5 calls) returned 5 distinct vectors; EAT 0.52–0.63, IDLE 0.01–0.02. Probabilities arrive rounded to 0.01; key order in `probabilities` varies between responses.

**Why `bucketed` was added** (D7, human decision on 2026-09-19). Basis: vendor documentation “Jev 1.13 jaggedness” (reviewed by the vendor 2026-09-17), verbatim: “It struggles with tasks that require numeric precision”; “`jev-1.13` will perform better on semantic representations than numeric … Instead: do the conversion in code and pass in either the computed number or a named bucket.” SPEC §4.3 defines `naive` as fields and numbers only. The third mode adds the vendor-recommended format while retaining both specified modes. At this snapshot it exists only as a decision, without code or template.

Cost: 20 calls $0.000281; one call $0.000014 at 334 input tokens.

## 4. Speed and memory

**LIF** (`reports/perf.md`, 2026-09-19 22:11; Apple M3 Pro 6P+6E, 36 GB, Python 3.12.8; **battery power**; timer self-check: `sleep(10 ms)` overshoot 2.52 ms, not throttled). Protocol: connectome v783, 20 sugar GRNs at 150 Hz, 500 ms window, dt 0.1 ms, one process, graph in memory; 10 full trials and 10 trials stopping at the first MN9 spike, after one warm-up.

| Backend | t_load, s | First trial, s | s/trial p50 | Max | RTF p50 | Spikes/trial | Early stop t_sim p50, ms | Wall p50, s | Peak RSS, MiB |
|---|---|---|---|---|---|---|---|---|---|
| `brian2` (Cython, reference) | 0.44 | 19.15 | 1.355 | 1.380 | 0.37 | 6 328 | 30.6 | 0.299 | 2 260 |
| `event` (NumPy + Numba) | 0.10 | 0.15 | 0.174 | 0.187 | 2.88 | 6 299 | 29.6 | 0.002 | 1 587 |
| `torch-cpu` (float64) | 0.02 | 2.16 | 2.147 | 2.166 | 0.23 | 6 299 | 29.6 | 0.120 | 1 684 |
| `torch-mps` (float32) | 0.08 | 4.94 | 4.627 | 4.815 | 0.11 | 6 335 | 29.6 | 0.226 | 1 891 |

- Graph load Parquet → CSR: 0.29 s. Peak process RSS immediately after loading: ~1,500 MiB (separate measurement, 3 trials of 500 ms, `ru_maxrss`).
- Brian2 cross-check with identical input spikes, (neuron, step) pairs over two trials: `event` 12,804 of 12,804; `torch-cpu` 12,804 of 12,804; `torch-mps` 12,803 matching out of a union of 12,805.
- Recommended backend in `reports/perf.md`: `event`. Not yet approved by the human author.
- Separate observation: in interactive agent calls, `sleep(10 ms)` took ~104 ms (median).

**Jev**, client `t_wall` only, sequential calls in one keep-alive session through OpenRouter over HTTP/1.1, measured from the agent process:

| Run | n | p50, ms | p95, ms | First (cold) call, ms |
|---|---|---|---|---|
| 2026-09-19 | 20 | 405.4 | 527.7 | 772.1 |
| Same, excluding first call | 19 | 391.4 | 479.7 | — |
| 2026-09-20 | 5 | 495.9 | 599.2 | 615.6 |

The SPEC §6.2 benchmark (`fob latency bench`, 20 warm-up calls, grid states) had not been run; the command was a stub.

## 5. Environment on `dev`

No data. `arena/`, `RandomArbiter`, `FixedPriorityArbiter`, `OracleArbiter`, and `fob eval` were not implemented (M2 not started); `configs/env.yaml` did not exist. Oracle / fixed / random mean lifetime, death causes, and oracle mean energy were unmeasured.

## 6. Manual parameters

| Parameter | Value | Selection basis |
|---|---|---|
| `R_max` | **200 Hz**, provisional (`configs/encoding.yaml`, E1) | Implementer selected the upper end of the authors' input-rate examples: `model.py` uses `r_poi = 150 Hz`; `example.ipynb` says “By default, the neurons are excited at 200 Hz”; its second experiment uses 100 Hz. No source prescribes the chosen value. Not result-tuned: set before the first G1 run |
| `theta_eat` | **Unset** | EAT decoder not implemented |
| MN9 sliding rate-window length | **Unset** | — |
| `alpha` | **`null`** (`configs/encoding.yaml`) | Unset; no simulation used hunger |
| `T_sim` | 500 ms | SPEC §4.1 |

LIF parameters (`configs/lif.yaml`) copied unchanged from `model.py` `default_params`: v_0 = v_rst = −52 mV, v_th = −45 mV, t_mbr = 20 ms, tau = 5 ms, t_rfc = 2.2 ms, t_dly = 1.8 ms, w_syn = 0.275 mV, f_poi = 250; dt = 0.1 ms (not specified in `model.py`; Brian2 default).

### Complete `docs/ENGINEERED.md` at this snapshot (verbatim)

````markdown
# ENGINEERED — register of hand-made assumptions

SPEC rule 4: every manual assumption is recorded here. The connectome supplies wiring and signs;
everything listed below is **ours**, and conclusions must be read in its light. Gate G6 checks
how sensitive the results are to the numeric entries.

An entry is added **when the assumption enters the code**, with its value, where it lives, its
source (or "none — chosen by us"), and the date. Values may change only before preregistration
(SPEC §8); after that a change is a deviation and is reported as such.

## Register

| # | Assumption | Value | Lives in | Source | Added |
|---|---|---|---|---|---|
| E1 | `R_max` = **200 Hz**, the Poisson rate at stimulus strength 1.0 (**provisional**; final value at M3) | 200 Hz | `configs/encoding.yaml` | None for the value itself — chosen by us as the top of the range used in the authors' materials (`model.py` default 150 Hz; `example.ipynb` mentions 200 Hz and runs 100 Hz). G6 perturbs it by ±50% | 2026-09-19 (M1) |
| E2 | "Sugar GRNs" = the 21 right-hemisphere neurons listed in the authors' `example.ipynb`; **20** of them under connectome v783 (one root id no longer exists) | 21 / 20 ids | `data/circuits.yaml` | Authors' notebook. That these 21 are *the* sugar GRNs, and right hemisphere only, is the authors' choice, adopted unchanged | 2026-09-19 (M1) |
| E3 | MN9 = a single neuron, `720575940660219265` | 1 id | `data/circuits.yaml` | Authors' notebook (`id_mn9`). Only one MN9 (one side) is read out | 2026-09-19 (M1) |
| E4 | Stimulus → firing: a stimulated neuron is turned into a Poisson spike source (each event forces a spike; refractoriness disabled), as in `model.py` | — | `lif/*_backend.py` | Authors' `poi()`. It replaces sensory transduction entirely | 2026-09-19 (M1) |
| E5 | G1 metric: Spearman ρ over **all trials** (11 sugar levels × 10 repeats, `t_sim` = 500 ms, MN9 rate over the whole window), not over per-level means | see `configs/gates.yaml` | `validation/gates.py` | Chosen by us before the first gate run; the conservative variant | 2026-09-19 (M1) |

## Declared by the SPEC, to be registered when implemented

Listed so that none is forgotten; values are deliberately left open.

| Assumption | SPEC | Milestone |
|---|---|---|
| Sugar encoding: Poisson input to sugar GRNs at `sugar · R_max · (1 + alpha · hunger)` | §4.1 | M3 |
| Hunger gain `alpha` — the hunger modulation itself is an assumption, not a connectome property | §4.1 | M3 |
| Bitter encoding: `bitter · R_max` into bitter GRNs | §4.1 | M3 |
| Looming encoding: direct input to LPLC2 and LC4, **bypassing the retina**, `looming · R_max` | §4.1 | M3 |
| `R_max` — provisional value registered as E1; final at M3 | §4.1 | M3 |
| Trial window `T_sim = 500 ms`, stimulus on at `t = 0` | §4.1 | M3 |
| `EAT` read-out: sliding-window MN9 rate crossing `theta_eat` (window length and threshold) | §4.1 | M3 |
| `ESCAPE` read-out: a single DNp01 spike | §4.1 | M3 |
| First-to-threshold wins; no crossing → `IDLE` | §4.1 | M3 |
| Choice of neuron sets standing for "sugar GRNs", "bitter GRNs", LPLC2, LC4, MN9, DNp01 | §4.1 | M1 / M3 |
| Degree- and sign-preserving shuffle procedure | §4.2 | M3 |
| Jev prompt templates `naive` / `informed` (wording is ours; tuned on `dev` only) | §4.3 | M4 |
| Policy-grid resolution and interpolation scheme | §4.5 | M1 / M4 |
| All environment constants in `configs/env.yaml` | §3 | M2 |

## Not model assumptions, but choices that shape measured numbers

| # | Choice | Why | Added |
|---|---|---|---|
| T1 | `JevClient` performs no retries; one latency sample = one HTTP exchange | A retried call would hide several round trips in one sample | 2026-09-19 (M0) |
| T2 | Jev is reached **only** through OpenRouter's alpha Decisions endpoint (D12) | Jev's `t_wall` includes the OpenRouter hop (edge routing + upstream call) by design; there is no direct-API comparison | 2026-09-19 (M0), fixed 2026-09-20 |
| T4 | Only client-side wall time is measured (D10); latency is summarised as p50 / p95 (D14) | Human decision simplifying SPEC §6 | 2026-09-20 |
| T3 | `Decision.action` for Jev will be sampled from `probabilities`; the API's own `choice` (an argmax) is ignored | SPEC §4: action is sampled from `probs`, same rule for every arbiter | 2026-09-19 (M0) |
````

## 7. Deviations from `SPEC.md`

Human decisions (`docs/decisions.md`; `SPEC.md` itself had not been edited):

| # | SPEC section | Original specification | State at this snapshot |
|---|---|---|---|
| D1, D12 | §4.3 | Jev access, `JEV_API_KEY` | OpenRouter only, alpha Decisions endpoint; key `OPENROUTER_API_KEY`; Jev `t_wall` includes the OpenRouter hop |
| D2 | §4.5 | Jev: 225 points × 2 modes = 450 calls (1 per point) | `N_rep = 20` per point; cache retains every repetition |
| D7 | §4.3 | 2 state modes: `naive`, `informed` | 3 modes: added `bucketed` |
| D8 | §4.3 | Default `--max-calls` 30,000 | 100,000 in code; cross-run counter not implemented |
| D10 | §4, §6.1 | Three times: `t_wall`, `t_sim`, `t_server`; `Decision.t_server_ms` | Two: `t_wall` for all, `t_sim` for connectome; removed `t_server_ms` |
| D11 | §4.3, §6.2 | Connection / first-byte / total logging; 8 concurrent requests; network metadata (type, city, time of day) | Removed; D3 (`t_gateway` from OpenRouter metadata) superseded |
| D13 | §4.3 | Log model version | Pinned model family `typesafe/jev-1.13`; any other response aborts the run |
| D14 | §6.2, §9 | p50 / p90 / p99 | p50 / p95 |
| D4 | §4.1 | Connectome version unspecified | v783 (provisional); original paper used v630 |
| D5 | §6.2 | — | Human author reruns decision-grade timing from their terminal; not yet rerun |
| D6 | §10 | Python 3.11+ | 3.12 (Homebrew Python 3.12.8 in use) |

Implementation-level deviations and additions (not recorded as human decisions):

- Commands absent from SPEC §9: `fob info`, `fob jev smoke`. Unimplemented commands exit with code 3.
- Jev client does not use the official SDK or retry requests.
- `MockJevClient` implements delay with busy-waiting rather than `time.sleep`.
- Data checksums are Git blob SHA-1 values from the authors' pinned repository tree, rather than separately published checksums.
- Brian2 backend differs from `model.py`: build the network once and restore state between trials (`store`/`restore`); create `PoissonInput` objects once per (neuron, rate) pair and toggle their `active` flag; add early stopping checked every 1 ms of simulated time. Equations, threshold, reset, and parameters are copied verbatim from `model.py`.
- Implementer defined the G1 metric: ρ across all trials, 11 levels × 10 repetitions (E5).
- Implementer selected `R_max = 200 Hz` (E1).
- v783 stimulates 20 sugar GRNs instead of 21.
- SPEC §4.1 allows a non-reference backend to be checked against Brian2 on G1–G3; a spike-for-spike check with identical input was performed instead; G2–G3 did not exist.
- Raw Jev smoke-test responses were not saved (SPEC §4.3 requires raw logging; not yet implemented).
- Documents beyond SPEC §14 layout: `docs/decisions.md`, `docs/open_questions.md`, `docs/lif_model_notes.md`; configurations `configs/data.yaml`, `configs/encoding.yaml`, `configs/gates.yaml`.
- `reports/perf.md` was measured on battery power.
- Required reading not yet completed: Shiu et al. (Nature 2024), and the neuroai.science methodology article (SPEC §13 requires it before M3).
