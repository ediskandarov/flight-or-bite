# SPEC: Flight or Bite — fly connectome versus Jev

> **Historical specification, translated into English on 2026-10-06 (D65).** This preserves the original v0.3 design, including later-superseded defaults and milestones. For the executed protocol use [PREREG.md](PREREG.md) and [approved decisions](docs/decisions.md); for current results use [README.md](README.md) and the [final report](reports/final_report.md). All planned runs are complete.

Specification for Claude Code · v0.3 · September 19, 2026
Target machine: MacBook, Apple M3 Pro (arm64, no CUDA). Terminal interface only.
Repository `flight-or-bite`, package `flight_or_bite`, command `fob`.

---

## 0. Rules for Claude Code

1. Read the entire specification. Follow the milestones (section 11) without skipping ahead.
2. **Do not invent anything**: neuron IDs, model parameters, and Jev API formats must come from primary sources (section 13). If a source does not provide the information, stop and ask (section 12).
3. Connectome weights are frozen. No training, backpropagation, RL, or trainable readouts.
4. A negative result is valid. Do not tune parameters to fit results. Record every manual assumption in `docs/ENGINEERED.md`.
5. Out of scope: 3D, physical bodies, MuJoCo, web interfaces, animation, human players, CUDA backends.
6. Code, identifiers, and commits must be in English.

---

## 1. Goal

Compare two “System One” candidates on food-versus-threat arbitration along two axes: **decision quality** and **decision time**:
- **connectome** — LIF simulation of the Drosophila brain (Shiu et al. model, FlyWire);
- **Jev** (TypeSafe AI) — a model returning typed choices with calibrated probabilities, called **online**.

Research questions:
- **RQ1.** Does arbitration emerge between feeding and escape circuits in the LIF model, and does it depend on the real wiring?
- **RQ2.** Which arbiter is closer to the optimal policy in survival?
- **RQ3.** Where do the connectome and Jev psychometric curves diverge?
- **RQ4.** How well calibrated are Jev probabilities relative to the oracle?
- **RQ5.** How long does each arbiter take to decide, and does that depend on conflict difficulty?

---

## 2. Design

The task is a sequence of trials without spatial navigation.

1. The environment provides `(sugar, bitter, looming)` ∈ [0,1]³ and `hunger` ∈ [0,1].
2. The arbiter chooses an action from `{EAT, ESCAPE, IDLE}`; decision time is recorded.
3. The environment samples the outcome and updates energy.

Two arbiter execution modes:
- **Table mode** — policy `π(action | sugar, bitter, looming, hunger)` and latency distributions are estimated on a grid; episodes are sampled from tables. Used for large-scale evaluation (1000 episodes).
- **Online** — each decision is made live: an actual Jev network call or an actual LIF simulation. Used for timing, live episodes, and checking table accuracy.

---

## 3. Environment (`arena/`)

Defaults are in `configs/env.yaml`; changes are allowed only before preregistration.

- `energy` ∈ [0, 100], initially 50; `hunger = 1 - energy/100`; episode limit 500 trials.
- Food is present with probability 0.5 (`sugar ~ U(0.2, 1)`), otherwise `sugar = 0`.
- Food is toxic with probability 0.25 (`bitter ~ U(0.3, 1)`), otherwise `bitter ~ U(0, 0.1)`.
- A threat is real with probability 0.2. `looming` is a noisy cue: `clip(N(0.7, 0.2))` with a threat, `clip(N(0.2, 0.2))` without one.
- Metabolism: −1 per trial.
- `EAT`: `+12·sugar`; if toxic, `−15·bitter`; with a real threat, death probability 0.6.
- `ESCAPE`: −3; the threat cannot kill the agent.
- `IDLE`: with a real threat, death probability 0.3.
- Death also occurs at `energy ≤ 0`.
- **Deadline (`deadline_ms` option, disabled by default):** if decision time exceeds the deadline, replace the action with `IDLE` (“missed deadline”).

Requirements: deterministic given a seed; `reset(seed) -> obs`, `step(action) -> obs, done, info`. Seeds: `dev` 0–999, `test` 100000–100999. Access to `test` requires `--unlock-test`; each access is logged in `runs/test_access.log`.

---

## 4. Arbiters (`arbiters/`)

```python
@dataclass
class Decision:
    probs: dict[Action, float]
    action: Action            # sampled from probs
    t_wall_ns: int            # wall-clock time from request to action
    t_sim_ms: float | None    # connectome only
    t_server_ms: float | None # Jev only, if returned by the API
    meta: dict                # cache_hit, backend, model_version, ...

class Arbiter(Protocol):
    name: str
    def decide(self, obs: Observation, rng) -> Decision: ...
```

### 4.1 ConnectomeArbiter

**Model.** Shiu et al., Nature 2024: LIF, uniform neuron parameters, weights from a signed connectivity matrix multiplied by one global constant. Source: `philshiu/Drosophila_brain_model` (Brian2). Simulate the entire graph; do not extract a subnetwork without approval.

**Backend for M3 Pro** — select at M1 based on measurements:
1. **Brian2 on CPU** (Cython or C++ standalone) — reference implementation; start here.
2. **Custom event-driven LIF in NumPy/Numba**: CSR graph; each step processes outgoing edges only from neurons that spiked; parallelize trials with processes.
3. **PyTorch MPS.** Sparse tensor support on MPS is limited: propagate spikes using `index_add_`/scatter over an edge list, verify on a toy graph, and fall back to CPU if needed.

Do not consider CUDA backends. Any non-reference backend must pass a Brian2 cross-check on G1–G3. Online mode requires **stepwise execution with early stopping** (load the graph once, reset state between trials).

**Sensory encoding (manual; document it):**
- `sugar` → Poisson input to sugar GRNs at rate `sugar · R_max · (1 + alpha · hunger)`. Hunger amplification is an assumption.
- `bitter` → input to bitter GRNs at `bitter · R_max`.
- `looming` → input directly to LPLC2 and LC4 (bypassing the retina), at `looming · R_max`.

**Motor decoding (manual):** trial window `T_sim = 500 ms`, stimulus onset at `t = 0`.
- `EAT` — the sliding MN9 rate crosses `theta_eat`.
- `ESCAPE` — a DNp01 spike (giant fiber).
- The first threshold crossing wins; the simulation **stops** there. No crossing within `T_sim` means `IDLE`.
- `t_sim_ms` = simulated time of threshold crossing (for `IDLE`, `T_sim`).

**Neuron IDs** must come from FlyWire/Codex annotations and the original repository, recorded in `data/circuits.yaml` with a `provenance` field.

### 4.2 ShuffledConnectomeArbiter
The same pipeline on a graph shuffled while preserving degrees and signs. 20 independent seeds.

### 4.3 JevArbiter
- At M0, read the official documentation and write `docs/jev_api_notes.md`: endpoint, authentication, `state`, question (choice / score / noul), and response formats, limits, version, and **whether the API returns server processing time**. Do not guess signatures.
- `JevClient` (real) and `MockJevClient` (test stub with configurable delay).
- Question: choice from `["EAT", "ESCAPE", "IDLE"]`; retain all option probabilities.
- Two state modes, both reported: `naive` (fields and numbers only) and `informed` (also describes environment rules, without optimal-policy hints). Templates in `configs/jev_prompts/`, tuned only on `dev`.
- **Online by default.** Use disk caching only when building policy tables or rebuilding reports. Force caching off in every timing mode; records with `cache_hit = true` never enter latency statistics.
- Persistent HTTP session (keep-alive). Use client hooks to log, where available: connection time, time to first byte, and total time.
- Key from `JEV_API_KEY`; `--max-calls` guard (default 30,000).
- Log the date, model version, raw responses, and request size.

### 4.4 Baselines and oracle
- `RandomArbiter`.
- `FixedPriorityArbiter`: `looming > 0.5 → ESCAPE`; otherwise `sugar > 0 and bitter < 0.3 → EAT`; otherwise `IDLE`.
- `OracleArbiter`: Bayesian threat posterior from `looming`, value iteration over discretized energy.
- Measure decision time identically for all arbiters; baselines define the lower end of the scale.

### 4.5 Policy tables (`policy_table/`)
- Default grid: `sugar` 5 × `bitter` 3 × `looming` 5 × `hunger` 3 = 225 points, `N_rep = 20` → 4,500 simulations.
- Shuffled graphs: two 1D slices, 10 points × 10 repetitions × 20 seeds = 2,000 simulations.
- Jev: 225 points × 2 modes = 450 calls.
- At each point, store both probabilities and **latency samples** (`t_sim_ms`, `t_wall_ns` for every repetition and outcome).
- Linear probability interpolation with renormalization; sample latency from the nearest node.
- Resumable computation (Parquet shards); overnight runs under `caffeinate -i`.
- After the M1 benchmark, propose the final grid size to the human author.

---

## 5. Validity gates (`validation/`)

Run before comparing against Jev. Each test writes `reports/gates/<gate>.json`: `passed`, `metric`, `threshold`, `details`.

| # | Gate | Criterion |
|---|---|---|
| G1 | Sugar → MN9 | MN9 rate increases monotonically with `sugar` (Spearman ρ > 0.8) |
| G2 | Bitter suppresses sugar | Increasing `bitter` reduces `p_eat` by at least 20% |
| G3 | Looming → DNp01 | `p_escape` increases monotonically with `looming` (ρ > 0.8) |
| G4 | Real versus shuffled | G1–G3 metrics lie outside the 95% null distribution across 20 shuffles |
| G5 | Ablation | Silenced DNp01 → `p_escape ≈ 0`; silenced MN9 → `p_eat ≈ 0` |
| G6 | Robustness | G1–G3 direction and monotonicity persist under ±50% changes to `R_max`, the global constant, and `alpha` |
| G7 | Conflict | With simultaneous `sugar` and `looming`, behavior differs statistically from an independent race model |

**G7 addresses RQ1.** Null model: circuits are independent; action is determined by a race between separately measured `t_sim` latencies. No difference means no arbitration in the wiring, only two reflexes. Continue the Jev comparison with the label “connectome = race of reflexes.”

Failure of G1–G3 or G5 → stop and ask the human author. Failure of G4 → publish the negative result. Failure of G6 → state in the report: “conclusions depend on manually chosen parameters.”

---

## 6. Decision time (`timing/`)

### 6.1 Three distinct times — keep them separate
| Quantity | Arbiter | Meaning |
|---|---|---|
| `t_wall` | all | Actual time from request to completed action on this machine and network |
| `t_sim` | connectome | Simulated time from stimulus onset to threshold crossing — the model's “biological” latency |
| `t_server` | Jev | Server processing time, **only if returned by the API**; otherwise empty |

Jev `t_wall` includes the network and depends on location and provider; connectome `t_wall` depends on this Mac. These are operational measurements, not intrinsic model properties; say so in the report. TypeSafe's speed claims concern comparisons with LLMs; this project does not test those claims.

### 6.2 Method
- Timer: `time.perf_counter_ns()`.
- **Jev:** sequential calls, one keep-alive session, caching disabled. The first 20 calls are warm-up: exclude them from primary statistics, but report the first call's cold latency separately. Sample states uniformly over the grid to cover easy and difficult conflicts. Separate throughput test: 8 concurrent requests, if rate limits permit.
- **Connectome:** one process, no parallel workers, graph already in memory (`t_load` reported separately). `t_wall` includes input generation and simulation up to early stopping. Compute real-time factor `RTF = elapsed t_sim / t_wall`.
- Before timing, record metadata: network type (Wi-Fi/wired), city, time of day, AC or battery power.
- Report p50 / p90 / p99 and ECDF; mean only as a supplement.

### 6.3 Analyses
- **A. Latency table** for all arbiters: `t_wall` p50/p90/p99; additionally `t_sim` and RTF for connectome; for Jev, cold start, connection / first byte / total breakdown, and `t_server` if available.
- **B. Speed versus quality** — the project's main figure: X is `t_wall` p50 (log scale), Y is `% of oracle`, one point per arbiter with CIs on both axes. Show connectome twice: using `t_wall` and `t_sim`.
- **C. Chronometric curves (RQ5).** Latency as a function of conflict difficulty `d = 1 − |p_escape − p_eat|` at each grid point. Hypothesis: connectome `t_sim` increases near the decision boundary (as in a race to threshold), whereas Jev `t_wall` is independent of difficulty (one pass). Test: Spearman correlation between `d` and latency, bootstrap CI.
- **D. Deadline sweep.** `deadline_ms` ∈ {1, 3, 10, 30, 100, 300, 1000, 3000}; survival as a function of deadline. Two tracks: `wall` (all use `t_wall`) and `native` (connectome uses `t_sim`, others use `t_wall`). Shows the time budget at which each arbiter becomes viable.

---

## 7. Quality evaluation (`eval/`)

**Primary quality metric:** mean lifetime in trials (censored at 500) over 1000 test episodes, table mode, no deadline.
- Paired comparison on identical seeds; bootstrap with 10,000 resamples, 95% CI for the difference; declare a winner only if the CI excludes zero.
- `% of oracle = (L − L_random) / (L_oracle − L_random)`.

**Live episodes (table validation):** 50 test episodes online for Jev and connectome. Compare with table results on the same seeds: survival difference and Jensen–Shannon divergence between live responses and interpolated tables at visited states. A substantial discrepancy means the grid is too coarse; notify the human author.

**“Most fly-like” (RQ3):** logistic fits to `p_escape(looming)` and `p_eat(bitter)` slices; compare threshold and slope across connectome, Jev, and oracle; mean JS divergence over the grid.

**Calibration (RQ4):** Brier score and reliability table for `p_escape` against “ESCAPE is optimal according to the oracle.”

**Secondary:** final energy, causes of death (starvation / predator / toxin / missed deadline), decision cost, argmax results.

---

## 8. Preregistration

Commit `PREREG.md` before the first access to `test`: hypotheses (including the chronometric hypothesis), configuration and Jev template hashes, grid, metrics, gate thresholds, statistics, timing protocol, deadline set, and secondary analyses.

`--unlock-test` fails if `PREREG.md` is absent or hashes do not match. Label everything not specified in advance as **exploratory**.

---

## 9. Terminal interface (`cli/`)

Command `fob` (Typer + Rich). Output: tables, progress bars, and Unicode histograms; plots only as static PNGs in `reports/figures/`.

| Command | Purpose |
|---|---|
| `fob fetch-data` | Download the connectome and verify checksums |
| `fob perf` | Benchmark LIF backends → `reports/perf.md` |
| `fob gate G1` / `fob gates` | Gates and pass/fail summary |
| `fob table build --arbiter connectome\|shuffled\|jev` | Build a resumable policy table |
| `fob table show --arbiter X --slice looming` | Show a policy and latency slice |
| `fob latency bench --arbiter jev\|connectome\|all --n 1000` | Benchmark under protocol 6.2 |
| `fob latency show` | Terminal p50/p90/p99 table and log-scale histograms |
| `fob live --seed N` | Live episode: both arbiters online on identical stimuli (see below) |
| `fob eval --split dev\|test [--unlock-test] [--deadline-sweep]` | Evaluate and show a table with CIs |
| `fob replay --seed N --arbiter X` | Text log of a table-mode episode |
| `fob report` | Build `reports/final_report.md` and PNGs from artifacts |

**`fob live`** — one line per trial: number, stimuli, then each arbiter's action, probabilities, and decision time with a log-scale bar (Unicode blocks, shared scale). Flag disagreements. Footer: running p50/p95 for each arbiter and a “who answered first” counter. Example:

```
 t=042  sugar 0.71  bitter 0.04  loom 0.63
   connectome  ESCAPE  0.81   sim  18.4 ms ▇▇▇▇        wall  240 ms ▇▇▇▇▇▇▇▇
   jev         EAT     0.55                            wall   61 ms ▇▇▇▇▇▇      ≠
```

**Report figures** (Matplotlib): speed versus quality; latency ECDF; chronometric curves; deadline sweep (two tracks); `p_escape(sugar, looming)` heatmaps; psychometric curves; survival curves; reliability diagrams.

---

## 10. Environment and reproducibility

- macOS arm64, Python 3.11+, `uv`, lockfile; Apple Silicon wheels only.
- Log chip, core count, and memory at startup. Default worker count = performance-core count (except timing runs, which use one process). If memory is insufficient, reduce workers, not the graph.
- YAML + Pydantic configurations. Each run writes configuration, Git hash, seeds, versions, logs, and results to `runs/<timestamp>_<name>/`.
- Policy tables, latency samples, and raw Jev responses must suffice for `fob report` to rebuild everything without simulations or API calls.
- Tests (`pytest`): environment, deadline, oracle on a toy MDP, interpolation, statistics, cache and disabling it during timing, timers with a known-delay `MockJevClient`, LIF early stopping on a synthetic graph.
- FlyWire data: CC BY-NC 4.0; do not commit; provide attribution in `README`. Non-commercial project.

---

## 11. Milestones

**M0 — Scaffold.** Repository, `uv`, CLI skeleton, `MockJevClient`, `docs/jev_api_notes.md`, `docs/sources.md`. If Jev is accessible, run a 20-call smoke test displaying latency.
Acceptance: passing `pytest`; list of questions for the human author.

**M1 — LIF on Mac.** Load the connectome, implement the Shiu model in Brian2, reproduce G1. Run `fob perf` on the candidates in 4.1, including RTF and early stopping.
Acceptance: G1 passed; `reports/perf.md` with backend and grid-size recommendations. **Stop and wait for confirmation.**

**M2 — Environment and oracle.** `arena/` with deadlines, baselines, `OracleArbiter`.
Acceptance: oracle significantly outperforms baselines on `dev`; if its lead over `FixedPriority` is below 10%, propose an environment-parameter change.

**M3 — Gates.** Encoding, decoding with `t_sim`, shuffling, ablations, sensitivity, race model.
Acceptance: all `reports/gates/*.json` and summary `reports/gates.md`. **Stop for a human decision.**

**M4 — Tables and timing.** Policy tables with latency samples; `fob latency bench` for all arbiters; working `fob live`.
Acceptance: Parquet artifacts, `reports/latency.md`, Jev usage within `--max-calls`.

**M5 — Final.** `PREREG.md` → evaluation on `test` with a deadline sweep and 50 live episodes → `fob report`.
Acceptance: report with quality and timing tables, figures, limitations, and exploratory work; successful rebuild from artifacts.

---

## 12. When to stop and ask

- A neuron ID or cell type cannot be found.
- Jev documentation is unavailable or contradictory, or API access is unavailable.
- Jev limits prevent the timing protocol in 6.2.
- The graph does not fit in memory, or estimated grid computation exceeds 24 hours.
- A backend cannot support early stopping while matching Brian2.
- G1–G5 fail.
- There is a desire to change parameters, thresholds, or metrics after viewing results.
- Usage would exceed `--max-calls`.
- There is a temptation to add a trainable component.

Format: blocker, options, recommendation, and rationale.

---

## 13. Sources

- Shiu et al., Nature 2024 — https://doi.org/10.1038/s41586-024-07763-9
- https://github.com/philshiu/Drosophila_brain_model
- https://github.com/eonsystemspbc/fly-brain (ports to other backends, for cross-checking)
- FlyWire — https://flywire.ai · Codex — https://codex.flywire.ai
- Jev: https://typesafe.ai/blog/introducing-system-one-models-and-jev · https://developers.cloudflare.com/ai/models/typesafe/jev/ · https://www.langchain.com/blog/building-a-harness-with-jev
- Methodology (read before M3): https://www.neuroai.science/p/are-flies-playing-beat-saber
- Example shuffle control: https://github.com/webergithub/fruitfly-lab
- Project catalog, including Apple MPS execution: https://github.com/cobanov/awesome-fly

---

## 14. Repository layout

```
flight-or-bite/
├── SPEC.md
├── PREREG.md            # added at M5
├── pyproject.toml
├── configs/             # env.yaml, lif.yaml, grid.yaml, timing.yaml, jev_prompts/
├── data/                # git-ignored except circuits.yaml
├── docs/                # ENGINEERED.md, jev_api_notes.md, sources.md
├── src/flight_or_bite/
│   ├── arena/  arbiters/  lif/  policy_table/
│   ├── validation/  timing/  eval/  cli/
├── tests/
├── runs/                # .gitignore
└── reports/             # gates/, figures/, perf.md, latency.md, final_report.md
```

In reports, use “LIF simulation of the connectome,” “circuit,” “arbiter,” and “policy.” Do not write “the fly decided,” “uploaded fly,” or “consciousness”: the connectome is a static map; all dynamics are defined by us.
