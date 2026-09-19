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
| — | *(no model assumptions are in the code yet — M0 is scaffolding only)* | | | | |

## Declared by the SPEC, to be registered when implemented

Listed so that none is forgotten; values are deliberately left open.

| Assumption | SPEC | Milestone |
|---|---|---|
| Sugar encoding: Poisson input to sugar GRNs at `sugar · R_max · (1 + alpha · hunger)` | §4.1 | M3 |
| Hunger gain `alpha` — the hunger modulation itself is an assumption, not a connectome property | §4.1 | M3 |
| Bitter encoding: `bitter · R_max` into bitter GRNs | §4.1 | M3 |
| Looming encoding: direct input to LPLC2 and LC4, **bypassing the retina**, `looming · R_max` | §4.1 | M3 |
| `R_max` | §4.1 | M1 (G1) / M3 |
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
| T2 | Jev is reached through **OpenRouter's alpha Decisions endpoint**, not `api.typesafe.ai` | Direct access is invite-only; the OpenRouter key works today. Jev's `t_wall` therefore includes the OpenRouter hop (edge routing + upstream call). `JevClient` switches to the direct path automatically if `JEV_API_KEY` appears | 2026-09-19 (M0) |
| T3 | `Decision.action` for Jev will be sampled from `probabilities`; the API's own `choice` (an argmax) is ignored | SPEC §4: action is sampled from `probs`, same rule for every arbiter | 2026-09-19 (M0) |
