# LIF backend benchmark

Generated 2026-09-19T22:11:31+04:00 by `fob perf`; raw numbers in `runs/20260919T220909_perf/perf.json`.

## Conditions

- Host: Apple M3 Pro, 6P + 6E cores, 36.0 GB, Darwin 24.6.0, Python 3.12.8.
- Power: Now drawing from 'Battery Power'.
- Timer throttling self-check: `sleep(10 ms)` overshoots by a median of 2.52 ms (max 2.56 ms) -> **not throttled**.
- Connectome v783: 138,639 neurons, 15,091,983 edges; parquet -> CSR in 0.29 s.
- Protocol (SPEC §6.2): one process, graph in memory, 20 sugar GRNs at 150 Hz, window 500 ms, dt 0.1 ms. `t_wall` covers input generation, state reset and simulation. 10 full trials and 10 early-stop trials (first MN9 spike) per backend, after one warm-up trial.

## Results

| Backend | t_load, s | First trial, s | Full trial wall p50, s | max, s | **RTF p50** | Spikes / trial | MN9, Hz | Early stop: fired | t_sim p50, ms | wall p50, s |
|---|---|---|---|---|---|---|---|---|---|---|
| `brian2` | 0.44 | 19.15 | 1.355 | 1.380 | **0.37** | 6,328 | 77.6 | 100% | 30.6 | 0.299 |
| `event` | 0.10 | 0.15 | 0.174 | 0.187 | **2.88** | 6,299 | 76.2 | 100% | 29.6 | 0.002 |
| `torch-mps` | 0.08 | 4.94 | 4.627 | 4.815 | **0.11** | 6,335 | 78.0 | 100% | 29.6 | 0.226 |
| `torch-cpu` | 0.02 | 2.16 | 2.147 | 2.166 | **0.23** | 6,299 | 76.2 | 100% | 29.6 | 0.120 |

RTF = simulated time / wall time; above 1 is faster than real time. *First trial* includes
one-off costs (code generation, cache warm-up) and is excluded from the other columns.

## Verification against the Brian2 reference

Input spikes recorded in a Brian2 trial are replayed into the candidate; all spikes of the
whole network are then compared as (neuron, time step) pairs over two trials.

| Backend | Identical pairs | Union | Verdict |
|---|---|---|---|
| `event` | 12,804 | 12,804 | **bit-identical** |
| `torch-mps` | 12,803 | 12,805 | differs |
| `torch-cpu` | 12,804 | 12,804 | **bit-identical** |

## Cost of the default grid (SPEC §4.5)

| Backend | connectome (225 points x 20) | shuffled (2 slices) | both, 1 process | both, 6 workers |
|---|---|---|---|---|
| `brian2` | 1.7 h | 45 min | 2.4 h | 24 min |
| `event` | 13 min | 6 min | 19 min | 3 min |
| `torch-mps` | 5.8 h | 2.6 h | 8.4 h | 1.4 h |
| `torch-cpu` | 2.7 h | 1.2 h | 3.9 h | 39 min |

Extrapolated from the sugar-only trial above, without early stopping. Trials that also
drive the looming channel will activate more of the network and cost more; that is unknown
until the LPLC2 / LC4 sets exist (M3). The multi-worker column assumes linear scaling.

## Recommendation

**Backend: `event`** — RTF 2.88, 7.8x the Brian2 reference, and bit-identical to Brian2 on replayed input.
Brian2 stays in the test suite as the reference. Only backends that passed verification
are eligible; a faster but unverified backend is never recommended.

### Grid size — proposal for the human (SPEC §4.5)

Connectome cost uses `event` at 0.174 s per trial on 6 workers; Jev cost assumes 0.4 s per sequential call and 3 state modes.

| Option | Grid (sugar x bitter x looming x hunger) | Points | Connectome sims | Connectome time | Jev calls | Jev time |
|---|---|---|---|---|---|---|
| A. SPEC default | 5 x 3 x 5 x 3 | 225 | 4,500 (N_rep 20) | 2 min | 13,500 (N_rep 20) | 1.5 h |
| B. finer stimulus axes | 7 x 5 x 7 x 5 | 1,225 | 24,500 (N_rep 20) | 12 min | 36,750 (N_rep 10) | 4.1 h |
| C. fine | 9 x 5 x 9 x 5 | 2,025 | 60,750 (N_rep 30) | 29 min | 60,750 (N_rep 10) | 6.8 h |

The connectome is no longer the bottleneck: Jev's sequential latency is. Suggested: **B**,
to be confirmed after M3, when the cost of trials with the looming channel is known. Finer
stimulus axes matter most for RQ3 (psychometric thresholds and slopes) and for the
interpolation error checked by the live episodes (SPEC §7).
