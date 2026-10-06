# Flight or Bite

Food-vs-threat arbitration by two "System One" candidates, compared on decision quality and
decision time:

- a **LIF simulation of the *Drosophila* connectome** (Shiu et al., *Nature* 2024; FlyWire), with
  frozen weights and hand-engineered sensory encoding / motor decoding;
- **Jev** (TypeSafe AI), a model returning typed choices with calibrated probabilities, called online.

The full specification is in [SPEC.md](SPEC.md). A negative result is a valid result.
Every hand-made assumption is recorded in [docs/ENGINEERED.md](docs/ENGINEERED.md).

Status (verified 2026-10-06): **all planned runs complete; final report available**.
All 14 hashes in [PREREG.md](PREREG.md) match. The connectome table has 24,500 rows;
each of the four Jev tables has 12,250 rows across two passes separated by at least 12 hours.
The [final report](reports/final_report.md) includes the main online test (300 paired
episodes across five arbiters), latency benchmark, and secondary sampled test (100 paired
episodes). Both online tests completed without Jev retries or stops.
Main mean lifetime: Jev informed 55.39 vs connectome 23.90 trials; paired difference
+31.49 (95% CI [28.06, 34.91]). Secondary sampled lifetime: 29.97 vs 24.06;
paired difference +5.91 (95% CI [0.63, 11.03]). The secondary analysis does not determine
the winner of the main comparison. G6 failed: **выводы зависят от ручных параметров**.

Protocol latency benchmark: 1,000 timed decisions per arbiter, no failures, AC power
and timer checks passed. Median wall time is 54.4 ms for the connectome and 354.7 ms
for Jev informed (including network and OpenRouter).
Additional direct TypeSafe benchmark (D64): all four modes, 1,000 timed calls plus
20 warm-up calls each, no errors. Original OpenRouter data are preserved.
See the [provider comparison](reports/latency_typesafe/comparison.md): informed wall-time
p50 / p95 is 304.8 / 408.8 ms direct, versus 354.7 / 479.1 ms through OpenRouter.
This is an additional comparison between separate runs; provider snapshot identity is unverified.
Estimated direct TypeSafe spend, including probes: $0.099440544 from the user-reported $5.00
opening balance; [spend ledger](reports/direct_typesafe/spend.json). Actual provider balance
has not been queried. The combined project call ledger is 80,580 / 100,000.

No planned runs remain. The [terminal run instructions](reports/run_instructions.md) are
retained for provenance; do not repeat the completed confirmatory analyses or test runs.
To rebuild the report from saved artifacts without API calls: `uv run fob report`.

Current handoff: [docs/handoff.md](docs/handoff.md); approved protocol changes:
[docs/decisions.md](docs/decisions.md).

Validity gates in [reports/gates.md](reports/gates.md): G1–G5 and G7 passed;
G6 (robustness) failed for 2 of 11 variants, accepted with the stated limitation (D41).
Jev templates [v1 are approved](reports/jev_templates.md) (D46).
Brian2 cross-check: [reports/crosscheck_brian2.md](reports/crosscheck_brian2.md).
M1: [reports/perf.md](reports/perf.md). M2: [reports/eval_dev.md](reports/eval_dev.md).
Exploratory reports: `reports/probe_*.md`, `reports/calibration.md`, `reports/grid_loss.md`, `reports/env_sweep.md`.
See SPEC §11 for milestones.

## Setup

Target: macOS arm64 (Apple Silicon), Python 3.12 via `uv`. No CUDA.

```bash
uv sync
uv run pytest
uv run fob --help
uv run fob info
uv run fob fetch-data      # ~190 MB connectome, verified against the authors' repository
uv run fob gates           # formal gates G1-G7 (about 1.5 h); `fob gates --summary` prints the table
uv run fob eval --split dev     # baselines and oracle on 1000 dev episodes -> reports/eval_dev.md
uv run fob replay --seed 3 --arbiter oracle          # text log of one episode
uv run fob table build --arbiter oracle              # policy table -> reports/tables/oracle/
uv run fob table show --arbiter oracle --slice looming --at sugar=0.75
caffeinate -i uv run fob perf   # backend benchmark -> reports/perf.md (run on AC power)
```

## Jev smoke test

```bash
uv run fob jev smoke --mock            # offline, MockJevClient
uv run fob jev smoke --n 20            # 20 real calls, per-call latency (~$0.0003)
```

Jev is reached through OpenRouter's alpha Decisions endpoint, model pinned to
`typesafe/jev-1.13`. The key is read from `OPENROUTER_API_KEY` (environment or a git-ignored
`.env` in the working directory). Only client-side wall time is measured.

API details, with sources: [docs/jev_api_notes.md](docs/jev_api_notes.md).

## Layout

```
configs/             env.yaml, lif.yaml, grid.yaml, timing.yaml, jev_prompts/
data/                connectome files (git-ignored) and circuits.yaml
docs/                ENGINEERED.md, jev_api_notes.md, sources.md, open_questions.md
src/flight_or_bite/  arena/ arbiters/ lif/ policy_table/ validation/ timing/ eval/ cli/
tests/
runs/                per-run outputs (git-ignored)
reports/             gates/, figures/, perf.md, latency.md, final_report.md
```

## Data attribution and licence

This project is **non-commercial**. It uses the FlyWire whole-brain connectome of *Drosophila
melanogaster*, distributed under **CC BY-NC 4.0**; the data are downloaded by `fob fetch-data`
and are never committed to this repository.

- Dorkenwald et al., "Neuronal wiring diagram of an adult brain", *Nature* 634 (2024).
- Schlegel et al., "Whole-brain annotation and multi-connectome cell typing of *Drosophila*",
  *Nature* 634 (2024).
- Shiu et al., "A *Drosophila* computational brain model reveals sensorimotor processing",
  *Nature* 634 (2024). https://doi.org/10.1038/s41586-024-07763-9 — model code:
  https://github.com/philshiu/Drosophila_brain_model (MIT).
- FlyWire: https://flywire.ai · Codex: https://codex.flywire.ai

See [docs/sources.md](docs/sources.md) for the full source list.

Terminology: reports say "LIF simulation of the connectome", "circuit", "arbiter", "policy".
The connectome is a static map; all dynamics are defined by us.
