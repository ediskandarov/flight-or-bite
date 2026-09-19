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
