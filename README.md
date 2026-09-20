# Flight or Bite

Food-vs-threat arbitration by two "System One" candidates, compared on decision quality and
decision time:

- a **LIF simulation of the *Drosophila* connectome** (Shiu et al., *Nature* 2024; FlyWire), with
  frozen weights and hand-engineered sensory encoding / motor decoding;
- **Jev** (TypeSafe AI), a model returning typed choices with calibrated probabilities, called online.

The full specification is in [SPEC.md](SPEC.md). A negative result is a valid result.
Every hand-made assumption is recorded in [docs/ENGINEERED.md](docs/ENGINEERED.md).

Status: **M3 done** — validity gates in [reports/gates.md](reports/gates.md): G1–G5 and G7 passed,
G6 (robustness) failed for 2 of 11 variants. Draft preregistration: [PREREG.draft.md](PREREG.draft.md).
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
