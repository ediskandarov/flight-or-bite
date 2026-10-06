# R5 probe: sugar input suppresses DNp01 (exploratory, decision D35)

Date: 2026-09-20. Protocol, including statistical test, recorded in the `scripts/probe_r5.py` docstring and committed **before** the run (`6fbf089`). Before that commit, only crash testing was performed (2 repetitions, unrelated seeds; output was not inspected and was deleted). Nothing changed after viewing results. Data: `runs/20260920T131530_probe-r5/probe_r5.json`.

Common setup: connectome v783, `event` backend, full 500 ms trials, calibrated encoding (sugar `R_max` 102.8 Hz, looming 2.34 Hz), hunger = 0. Trial outcome: at least one spike from either DNp01, yes/no. looming ∈ {0.6, 0.8, 1.0}, 40 repetitions, seeds 7,500,000+.
**Pairing:** each channel draws Poisson inputs from its own RNG stream (seed, channel), making looming input bitwise identical across conditions on the same seed. Control: looming-only on identical seeds.
**Prespecified test:** exact two-sided McNemar test, condition versus control separately at each looming level (primary); same test pooled across three levels (120 pairs) is additional. b counts pairs with a spike in control but not condition; c counts the reverse.

Control (looming-only): DNp01 spiked in 29/40, 40/40, 40/40 trials at looming 0.6 / 0.8 / 1.0; median first-spike `t_sim` 193 / 134 / 89 ms.

Cell format: control → condition; b, c; p.

## A. Specificity

Co-stimulus: 20 neurons at the rate corresponding to sugar = 0.6 (61.7 Hz).

| Co-stimulus | looming 0.6 | looming 0.8 | looming 1.0 | Pooled (additional) |
|---|---|---|---|---|
| (0) 20 sugar GRNs (reference) | 29/40 → 14/40; b=15, c=0; p=6.1e-05 | 40/40 → 25/40; b=15, c=0; p=6.1e-05 | 40/40 → 31/40; b=9, c=0; p=0.0039 | 109/120 → 70/120; b=39, c=0; p=3.6e-12 |
| (1) 20 bitter GRNs | 29/40 → 29/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 109/120 → 109/120; b=0, c=0; p=1 |
| (2) Random sensory neurons, set 1 (primary) | 29/40 → 29/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 109/120 → 109/120; b=0, c=0; p=1 |
| Set 2 (additional) | 29/40 → 29/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 109/120 → 109/120; b=0, c=0; p=1 |
| Set 3 | 29/40 → 29/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 109/120 → 109/120; b=0, c=0; p=1 |
| Set 4 | 29/40 → 29/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 109/120 → 109/120; b=0, c=0; p=1 |
| Set 5 | 29/40 → 22/40; b=7, c=0; p=0.016 | 40/40 → 32/40; b=8, c=0; p=0.0078 | 40/40 → 36/40; b=4, c=0; p=0.12 | 109/120 → 90/120; b=19, c=0; p=3.8e-06 |

Random sensory neurons: FlyWire annotations, `super_class == 'sensory'` and `cell_class != 'gustatory'`, present in v783: 16,018 neurons (visual 10,855, mechanosensory 2,656, olfactory 2,279, other 228); sample 20 without replacement using `numpy.random.default_rng(s)`. Set composition:

| Set (seed) | Classes |
|---|---|
| 1 | visual: 12, olfactory: 4, mechanosensory: 4 |
| 2 | visual: 12, mechanosensory: 4, olfactory: 4 |
| 3 | visual: 10, mechanosensory: 5, olfactory: 5 |
| 4 | visual: 16, mechanosensory: 3, olfactory: 1 |
| 5 | visual: 11, olfactory: 6, mechanosensory: 2, unknown_sensory: 1 |

- Sugar GRNs: DNp01 spikes disappear in all 39 discordant pairs and appear in none.
- Bitter GRNs and random sets 1–4: no discordant pairs out of 120; every trial matches control.
- Random set 5 (additional) produces suppression: 19 pairs versus 0. Which of its 20 neurons causes this was not investigated.

## B. Sugar dose

| sugar | MN9 rate, Hz | looming 0.6 | looming 0.8 | looming 1.0 | Pooled (additional) | First DNp01 spike t_sim p50, ms (pooled) |
|---|---|---|---|---|---|---|
| 0 (control) | 0.0 | 29/40 | 40/40 | 40/40 | 109/120 | 134 |
| 0.3 | 0.2 | 29/40 → 29/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 109/120 → 109/120; b=0, c=0; p=1 | 134 |
| 0.6 | 27.2 | 29/40 → 14/40; b=15, c=0; p=6.1e-05 | 40/40 → 25/40; b=15, c=0; p=6.1e-05 | 40/40 → 31/40; b=9, c=0; p=0.0039 | 109/120 → 70/120; b=39, c=0; p=3.6e-12 | 184 |
| 1.0 | 63.2 | 29/40 → 9/40; b=21, c=1; p=1.1e-05 | 40/40 → 19/40; b=21, c=0; p=9.5e-07 | 40/40 → 29/40; b=11, c=0; p=0.00098 | 109/120 → 57/120; b=53, c=1; p=6.1e-15 | 256 |

- Trials with a DNp01 spike (out of 120): 109 → 109 → 70 → 57 at sugar 0 → 0.3 → 0.6 → 1.0. No outcome changes at sugar 0.3; MN9 firing there is 0.2 Hz.
- Median first DNp01 spike `t_sim` among trials with a spike: 134 → 134 → 184 → 256 ms.

## C. Mediators

Definitions (from the protocol). S: neurons spiking in at least one of 40 sugar-only trials (sugar 0.6): 360 neurons, including 171 inhibitory. P: presynaptic partners of either DNp01: 862, including 322 active in at least one looming-only trial. M_all: inhibitory neurons in S with at least one edge onto P or DNp01. M_loom: same, restricted to looming-active partners or DNp01. Silence the set (all outgoing weights = 0) **in both control and sugar 0.6 condition**.

| Silenced | Silenced control: DNp01 spike at 0.6 / 0.8 / 1.0 | looming 0.6 | looming 0.8 | looming 1.0 | Pooled (additional) | Condition MN9 rate, Hz |
|---|---|---|---|---|---|---|
| None (part A) | 29/40 / 40/40 / 40/40 | 29/40 → 14/40; b=15, c=0; p=6.1e-05 | 40/40 → 25/40; b=15, c=0; p=6.1e-05 | 40/40 → 31/40; b=9, c=0; p=0.0039 | 109/120 → 70/120; b=39, c=0; p=3.6e-12 | 27.2 |
| M_all (97 neurons) | 29/40 / 40/40 / 40/40 | 29/40 → 30/40; b=3, c=4; p=1 | 40/40 → 38/40; b=2, c=0; p=0.5 | 40/40 → 39/40; b=1, c=0; p=1 | 109/120 → 107/120; b=6, c=4; p=0.75 | 107.4 |
| M_loom (25 neurons) | 29/40 / 40/40 / 40/40 | 29/40 → 29/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 40/40 → 40/40; b=0, c=0; p=1 | 109/120 → 109/120; b=0, c=0; p=1 | 31.2 |

- Silencing the 25 M_loom neurons removes the effect entirely: zero discordant pairs out of 120. The silenced control is unchanged (29 / 40 / 40).
- Silencing the 97 M_all neurons leaves discordant pairs in both directions (6 and 4); MN9 firing rises from 27 to 107 Hz.

M_loom membership (25 neurons), ordered by synapse count onto looming-active DNp01 partners and DNp01 itself (858 synapses total); types and transmitters from FlyWire annotations (`flyconnectome/flywire_annotations` @ `8587524c17`):

| root_id (v783) | cell_type | super_class | top_nt | Side | Synapses onto looming-active partners / DNp01 | Onto all partners / DNp01 | Directly onto DNp01 |
|---|---|---|---|---|---|---|---|
| `720575940621148948` | cL20 | visual_centrifugal | gaba | right | 361 | 590 | 0 |
| `720575940616018956` | CB0568 | central | gaba | left | 149 | 167 | 0 |
| `720575940623478115` | CB0009 | central | gaba | left | 66 | 103 | 0 |
| `720575940610803554` | CB0538 | central | glutamate | right | 59 | 83 | 0 |
| `720575940624163303` | CB3916 | central | gaba | center | 51 | 490 | 5 |
| `720575940609405635` | CB0538 | central | glutamate | left | 38 | 73 | 0 |
| `720575940623072013` | LT37 | visual_centrifugal | gaba | right | 32 | 32 | 0 |
| `720575940609133269` | CB0568 | central | gaba | right | 27 | 63 | 1 |
| `720575940628755815` | CB0890 | central | gaba | left | 21 | 39 | 0 |
| `720575940611160930` | CB0890 | central | gaba | right | 12 | 45 | 0 |
| `720575940631168057` | DNg60 | descending | gaba | left | 7 | 7 | 0 |
| `720575940629855787` | cL22a | visual_centrifugal | gaba | right | 6 | 60 | 0 |
| `720575940631340815` | CB3892b | central | gaba | center | 6 | 70 | 0 |
| `720575940620473547` | DNge098 | descending | gaba | left | 5 | 18 | 0 |
| `720575940620474278` | CB0865 | central | gaba | right | 3 | 6 | 0 |
| `720575940621777390` | CB0030 | central | gaba | right | 3 | 4 | 0 |
| `720575940615623867` | CB0182 | central | gaba | left | 2 | 43 | 0 |
| `720575940621057702` | CB0865 | central | gaba | left | 2 | 17 | 0 |
| `720575940634756203` | CB0072 | central | gaba | right | 2 | 45 | 0 |
| `720575940612537061` | CB0358 | central | gaba | right | 1 | 259 | 0 |
| `720575940620714150` | DNge046 | descending | gaba | right | 1 | 4 | 0 |
| `720575940628446010` | CB0021 | central | gaba | right | 1 | 5 | 1 |
| `720575940631714119` | CB0698 | central | gaba | right | 1 | 27 | 0 |
| `720575940635211115` | CB0865 | central | gaba | right | 1 | 4 | 0 |
| `720575940644758308` | DNge046 | descending | gaba | left | 1 | 6 | 0 |

Not investigated: which targets transmit the effect (directly stimulated LPLC2/LC4, other partners, or direct DNp01 synapses), and whether a subset of the 25 neurons is sufficient.

## D. Alternative looming encoding: fraction of neurons

Looming sets the number of stimulated LPLC2/LC4: x = looming · f_max · 314, k = ⌊x⌋ + Bernoulli(x − ⌊x⌋); random subset per trial, rate 100 Hz; others receive no stimulation (refractoriness removed only from stimulated neurons). Calibration uses the same target: P(ESCAPE) = 0.5 at looming 0.5, bisection over f_max, 50 trials per step, dev seeds 0–49.

| Step | f_max | Neurons at looming 0.5 | P(ESCAPE) |
|---|---|---|---|
| 1 | 0.50000 | 78.50 | 1.00 |
| 2 | 0.25000 | 39.25 | 1.00 |
| 3 | 0.12500 | 19.62 | 0.98 |
| 4 | 0.06250 | 9.81 | 0.82 |
| 5 | 0.03125 | 4.91 | 0.58 |
| 6 | 0.01562 | 2.45 | 0.18 |
| 7 | 0.02344 | 3.68 | 0.42 |
| 8 | 0.02734 | 4.29 | 0.54 |
| 9 | 0.02539 | 3.99 | 0.50 |

**f_max = 0.02539**, or 7.97 of 314 neurons at looming = 1 and 3.99 at 0.5. Independent dev seeds 500–549 give P(ESCAPE) at looming 0.5 = **0.36** (target 0.50; rate coding achieved 0.50).

Curve on seeds 500–549 (50 trials per level):

| looming | Expected neurons | P(DNp01 spike) | First DNp01 spike t_sim, ms: p50 [min–max] |
|---|---|---|---|
| 0.0 | 0.00 | 0.00 | — |
| 0.1 | 0.80 | 0.08 | 82 [44–214] |
| 0.2 | 1.59 | 0.16 | 99 [59–480] |
| 0.3 | 2.39 | 0.20 | 76 [38–270] |
| 0.4 | 3.19 | 0.26 | 96 [36–331] |
| 0.5 | 3.99 | 0.36 | 64 [29–367] |
| 0.6 | 4.78 | 0.50 | 94 [33–491] |
| 0.7 | 5.58 | 0.60 | 89 [32–475] |
| 0.8 | 6.38 | 0.68 | 70 [29–475] |
| 0.9 | 7.18 | 0.70 | 72 [29–410] |
| 1.0 | 7.97 | 0.82 | 72 [22–437] |

Repeat of part B with this encoding (control: 21/40, 27/40, 29/40; median `t_sim` 114 / 86 / 86 ms):

| sugar | looming 0.6 | looming 0.8 | looming 1.0 | Pooled (additional) | First DNp01 spike t_sim p50, ms (pooled) |
|---|---|---|---|---|---|
| 0.3 | 21/40 → 21/40; b=0, c=0; p=1 | 27/40 → 27/40; b=0, c=0; p=1 | 29/40 → 29/40; b=0, c=0; p=1 | 77/120 → 77/120; b=0, c=0; p=1 | 86 |
| 0.6 | 21/40 → 16/40; b=5, c=0; p=0.062 | 27/40 → 23/40; b=5, c=1; p=0.22 | 29/40 → 28/40; b=1, c=0; p=1 | 77/120 → 67/120; b=11, c=1; p=0.0063 | 90 |
| 1.0 | 21/40 → 14/40; b=7, c=0; p=0.016 | 27/40 → 19/40; b=9, c=1; p=0.021 | 29/40 → 28/40; b=1, c=0; p=1 | 77/120 → 61/120; b=17, c=1; p=0.00014 | 146 |

- Trials with a DNp01 spike (out of 120): 77 → 77 → 67 → 61 at sugar 0 → 0.3 → 0.6 → 1.0.
- In primary per-level tests at sugar 0.6, no level reaches p < 0.05 (0.062 / 0.22 / 1); at sugar 1.0, two of three do (0.016 / 0.021 / 1). At looming 1.0 there is only one discordant pair.
- First DNp01 spike `t_sim` with this encoding: median 64–98 ms across looming levels (rate coding: 193 → 89 ms at looming 0.6 → 1.0); within-level range ~25 to ~490 ms.

## Not included

- Multiple-comparison correction (not specified in the protocol; parts A–D have 3 primary tests per condition).
- Shuffled-graph testing; other looming levels; hunger (hunger = 0 throughout, so `alpha` has no effect).
- Identifying which neuron in random set 5 causes suppression or which targets mediate M_loom effects.
- Brian2 cross-check of these trials (backend checked on sugar input and a random graph).
