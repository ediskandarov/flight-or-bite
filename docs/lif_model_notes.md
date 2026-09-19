# LIF model notes (M1)

What was established about the reference model and how our backends relate to it. Sources:
`philshiu/Drosophila_brain_model` @ `91bdd1e7dc` (`model.py`, `utils.py`, `example.ipynb`,
`Readme.md`), read in full on 2026-09-19, and state traces of Brian2 2.10.1 on toy networks.
The paper itself (Shiu et al., *Nature* 2024) has **not** been read yet; nothing below relies on it.

## 1. The model, as written in `model.py`

```
dv/dt = (v_0 - v + g) / t_mbr : volt (unless refractory)
dg/dt = -g / tau               : volt (unless refractory)
threshold  v > v_th        reset  v = v_rst; w = 0; g = 0 * mV
synapse    on_pre: g += w,  w = (signed synapse count) * w_syn,  delay = t_dly
method     'linear' (exact integration)     dt: never set -> Brian2 default, 0.1 ms
```

Parameters are in `configs/lif.yaml`, copied verbatim with the citations given in the source.
`w_syn = 0.275 mV` is described there as the "Free parameter". `w = 0` in the reset assigns an
unused temporary — a no-op in the original as well; kept verbatim in our Brian2 backend.

**Stimulation** (`poi`): one `PoissonInput(N=1, rate=r_poi, weight=w_syn * f_poi)` per stimulated
neuron, acting on `v` directly. With `f_poi = 250` a single event adds 68.75 mV, i.e. always
forces a spike; stimulated neurons get `rfc = 0`. A stimulated neuron is therefore a Poisson spike
source at `r_poi`, not a neuron receiving graded input.

**Silencing** (`silence`): weights of all synapses *from* the neuron are set to 0. (`Readme.md`
says "to and from"; the code only does "from". We follow the code.)

**Inconsistency in the source:** `example.ipynb` says "By default, the neurons are excited at
200 Hz", while `model.py` has `r_poi = 150 * Hz`. The code wins; the 150 Hz example reproduces the
notebook's own numbers (below).

## 2. Step semantics that a re-implementation must copy

Brian2 runs each 0.1 ms step as: **state update -> threshold -> synapses (+ PoissonInput) -> reset**.
Established from `StateMonitor` traces on a 3-neuron chain:

| Fact | Evidence |
|---|---|
| A spike emitted in step *n* reaches its targets in step *n* + 18 (1.8 ms) | `g` of the target jumps from 0 to `w` between the samples of steps 49 and 50 for a spike in step 31 |
| A Poisson kick in step *s* makes the target fire in step *s* + 1 | kick is applied after the threshold check of step *s* |
| After a spike in step *n* the neuron is frozen for steps *n*+1 … *n*+21; updates resume at *n*+22 | `not_refractory` trace |
| **Synaptic input that arrives while the target is refractory is discarded** | target spiked at step 104; input delivered at step 124; `g` stayed exactly 0 afterwards. Brian2 gates `g += w` by `not_refractory` because `g` carries the `(unless refractory)` flag |
| Input arriving in the very step a neuron fires is lost | reset (`g = 0`) runs after the synapses slot |

The fourth row is not obvious from the equations. Our first implementation let refractory neurons
accumulate input and produced **~20% more spikes** (MN9: 107 Hz instead of 80 Hz) — a reminder
that "the same equations" is not "the same model".

## 3. Reproduction of the authors' example

Connectome v630, the 21 sugar GRNs of `example.ipynb` at 150 Hz, 1 s, our Brian2 backend:

| | Authors' notebook | Ours |
|---|---|---|
| Spikes per trial | "more than 400 000 spikes" over 30 trials -> >13 300 | 13 698 and 13 233 (two seeds) |
| Active neurons | "only about 400 neurons show activity" | 375 and 381 |
| MN9 rate | not stated in the notebook | 80 and 82 Hz |

## 4. Backends

| Backend | Precision | Relation to the reference |
|---|---|---|
| `brian2` (Cython code generation) | float64 | **the reference**; mirrors `model.py`, but builds the network once and restores state between trials |
| `event` (NumPy + Numba) | float64 | **bit-identical**: with Brian2's input spikes replayed, every spike of the whole connectome matches as a (neuron, step) pair — 13 698 / 13 698 and 13 233 / 13 233 |
| `torch-cpu` | float64 | bit-identical to Brian2 on replayed input (12 804 / 12 804) |
| `torch-mps` | **float32** (MPS has no float64) | **not** identical: on the full v783 graph 2 of 12 805 (neuron, step) pairs differ from Brian2 over two 500 ms trials (identical on a 200-neuron toy graph and on a 100 ms v630 trial). Rounding differences flip rare near-threshold crossings |

How the comparison works: our kernels are deterministic given a schedule of Poisson kicks. The
spikes of the stimulated neurons in a Brian2 trial are converted back into that schedule
(`replay_schedule`), so the rest of the network sees identical input in both simulators and can be
compared exactly instead of statistically. This is stricter than SPEC §4.1 asks for (agreement on
G1–G3).

`event` updates only neurons that activity has reached. This is exact, not an approximation: a
neuron at `v = v_0, g = 0` is a fixed point of the update. In the sugar trial 11 178 of 127 400
neurons (8.8%) are ever touched. Spikes of one step are delivered in neuron-index order, as in
Brian2, so that floating-point sums in `g` stay bit-identical.

Build notes: the interpreter `uv` selected (Homebrew Python 3.12.8) records `MacOSX14.sdk`, which is absent on this machine
(15.x and 26.x are installed); Brian2's Cython link step then fails with "library 'c++' not
found". `Brian2Backend` passes `-isysroot $(xcrun --show-sdk-path)` through
`prefs.codegen.cpp.extra_link_args`. No system change is needed.

## 5. Measured performance and G1 (details: `reports/perf.md`, `reports/gates/G1.json`)

500 ms sugar trial on v783, one process: `event` 0.174 s (RTF 2.88), `brian2` 1.355 s (0.37),
`torch-cpu` 2.147 s (0.23), `torch-mps` 4.627 s (0.11). With early stopping at the first MN9
spike (`t_sim` ≈ 30 ms) a decision costs `event` ≈ 2 ms of wall time. The PyTorch backends lose
because each of the 5 000 steps launches a dozen small kernels and synchronises with the host to
read which neurons fired, while the useful work per step is a handful of spikes.

G1 passes on both backends and both versions (ρ over all trials 0.944–0.966, threshold 0.8).
The MN9 response is sigmoidal in sugar: silent below 0.2 (40 Hz drive), steep between 0.2 and
0.4, saturating near 90 Hz. With `R_max` = 200 Hz the informative range of the sugar axis is
therefore narrow — to be weighed at M3 when `R_max` and `theta_eat` are fixed.

## 6. Connectome versions

| | Neurons | Edges | Sugar GRN ids of the example | MN9 id |
|---|---|---|---|---|
| v630 — "which the paper used" (`Readme.md`) | 127 400 | 14 687 178 | 21 / 21 | present |
| v783 — "public version" (`Readme.md`) | 138 639 | 15 091 983 | 20 / 21 | present |

`720575940620900446` does not exist in v783 (root ids change when a neuron is edited). Its
successor has not been looked up; until it is, v783 runs use 20 sugar GRNs. This is recorded in
`data/circuits.yaml` (`absent_in`) and enforced in code: any *other* missing id is an error.
