# Flight or Bite

A completed, preregistered comparison of **decision quality and decision time** in a
food-versus-threat task: a LIF simulation of the *Drosophila* connectome versus
**Jev** (TypeSafe AI).

Each arbiter receives sugar, bitterness, looming threat, and hunger observations, then
chooses `EAT`, `ESCAPE`, or `IDLE`. Food restores energy, escape costs energy, and a
missed threat can be fatal. The connectome uses a fixed neural graph with manually
specified input encoding and output decoding; Jev is queried online. Neither system
was trained or tuned on the test results.

**Status: complete, verified October 6, 2026.** All planned runs and the additional
direct TypeSafe latency benchmark are finished. The 14 preregistered configuration
and circuit hashes match. Documentation, generated reports, and figure labels are in English.

## Results

The primary test used **300 paired seeds and five arbiters** (1,500 episodes), with
native actions and no decision deadline.

| Arbiter | Mean lifetime, trials |
|---|---:|
| Oracle | 73.81 |
| Fixed-priority rule | 56.66 |
| Jev, informed | 55.39 |
| LIF connectome simulation | 23.90 |
| Random | 14.14 |

Jev's paired advantage over the connectome was **+31.49 trials**, with a 95% bootstrap
CI of **[28.06, 34.91]**. This meets the preregistered criterion for winning that
comparison. The descriptive fixed-priority versus Jev difference was +1.27 trials
(CI [−3.32, 5.87]); no significant difference was demonstrated.

In the **secondary test**, actions were sampled from returned probabilities over
100 paired seeds (500 episodes): Jev averaged **29.97** trials and the connectome
**24.06**, a paired difference of **+5.91 [0.63, 11.03]**. This analysis does not
determine the primary winner. Both online tests completed without Jev retries or stops.

### Decision time

Benchmarks were run by the author from a normal terminal on AC power, with 1,000 timed
decisions per arbiter or Jev mode and 20 warm-up calls per Jev mode. No benchmark
failures were recorded.

| Arbiter / API route | Median wall time, ms | p95, ms |
|---|---:|---:|
| LIF connectome simulation, local | 54.4 | 262.9 |
| Jev informed, OpenRouter | 354.7 | 479.1 |
| Jev informed, direct TypeSafe | 304.8 | 408.8 |

The direct informed median was approximately **14.1% lower** than OpenRouter's.
These were separate runs at different times; equivalence of provider model snapshots
is unverified. The full difference cannot be attributed to the intermediary.
API wall time includes network latency; local simulation wall time depends on the
computer. Simulated neural time (`t_sim`) is reported separately. These numbers do
not measure intrinsic model speed or a living fly's reaction time.

Original OpenRouter results remain in `reports/latency/`. Direct measurements are
stored separately in `reports/latency_typesafe/`; they supplement the primary experiment.

## Read the study

- [Final report](reports/final_report.md): primary and secondary outcomes, H1–H6,
  psychometrics, calibration, timing, figures, and limitations.
- [Direct TypeSafe versus OpenRouter](reports/latency_typesafe/comparison.md): all
  four Jev modes, matched benchmark states, provenance, and comparison limitations.
- [Preregistration](PREREG.md): frozen hypotheses, statistical criteria, seeds, and hashes.
- [Validity gates](reports/gates.md) and [Brian2 cross-check](reports/crosscheck_brian2.md).
- [Engineered assumptions](docs/ENGINEERED.md), [decision history](docs/decisions.md),
  and [handoff log](docs/handoff.md).
- [Original specification](SPEC.md) and [terminal run instructions](reports/run_instructions.md),
  retained as historical and reproducibility documents. Approved decisions and PREREG
  take precedence over superseded parts of the original specification.

**Key limitation: conclusions depend on manually chosen parameters.** G1–G5 and G7
passed; G6 robustness failed in 2 of 11 variants. The thresholds were not relaxed after
viewing results. A connectome is a static wiring map; this project's dynamics,
sensory encoding, and motor readout are engineered. The findings concern this task
and this simulation, not general intelligence or the behavior of a living fly.

The English translation was requested after the experiment (D65). Original-language
protocol text remains in Git history; hypotheses, thresholds, seeds, configuration
hashes, model prompts, and raw experimental data were preserved.

## Rebuild from saved artifacts

Target environment: macOS on Apple Silicon; validated with Python 3.12 and `uv`.
The repository includes a lockfile. No CUDA is used.

```bash
uv sync
uv run python -c "from flight_or_bite import prereg; prereg.check(); print('Frozen hashes match')"
uv run fob report
uv run fob latency show
```

`fob report` rebuilds the final Markdown report and PNG figures from existing
artifacts, without simulations or API calls. A checkout needs the experiment's
saved artifacts; run metadata and some raw logs live in the git-ignored `runs/`
directory. Missing artifacts are reported explicitly rather than fabricated.

```bash
uv run pytest
uv run fob --help
uv run fob info
```

The completed confirmatory analyses and test runs should not be repeated to tune
parameters. The archived [run instructions](reports/run_instructions.md) document
the original commands and recovery behavior. Any new experiment should be separate.

## API access and spend

The main experiment used `OPENROUTER_API_KEY`, requesting `typesafe/jev-1.13` through
OpenRouter Decisions; recorded responses were `typesafe/jev-1.13-20260917`.
The separate direct benchmark used `TYPESAFE_API_KEY` and pinned `jev-1.13.0` at
`https://api.typesafe.ai/v1/systemone`. Keys may be supplied through the environment
or a git-ignored `.env`; do not commit them. See [API notes](docs/jev_api_notes.md)
and [approved request templates](reports/jev_templates.md).

As of completion, the shared project ledger records **80,580 / 100,000 calls**.
Direct TypeSafe usage, including probes and benchmark warm-up, totals **4,201 calls**
and **2,367,632 input tokens**. Estimated spend is **$0.099440544**, leaving an
estimated **$4.900559456** from the user-reported $5.00 opening balance. The actual
provider balance was not queried. [Spend ledger](reports/direct_typesafe/spend.json).
These amounts cover direct TypeSafe calls only, not the project's OpenRouter usage.

## Repository layout

```text
configs/             Frozen environment, encoding, LIF, grid, timing, and Jev templates
data/                Downloaded connectome (git-ignored); tracked circuits.yaml
src/flight_or_bite/  Arena, arbiters, LIF, policy tables, validation, timing, evaluation, CLI
scripts/             Exploratory analyses and separate direct API benchmark
reports/             Final and historical reports, saved results, figures
docs/                Assumptions, sources, API notes, decisions, handoff
runs/                Per-run metadata and raw logs (git-ignored)
tests/               Offline tests and Brian2 reference checks
```

Policy tables contain 24,500 connectome rows and 12,250 rows for each of four Jev
modes. Jev tables use two passes separated by at least 12 hours. Earlier exploratory
reports retain their original dates and results; they are not current task lists.

## Data attribution and license

This project is **non-commercial**. It uses the FlyWire whole-brain connectome of
*Drosophila melanogaster*, distributed under **CC BY-NC 4.0**. Downloaded connectome
data are never committed. `uv run fob fetch-data` retrieves and verifies the data
when needed for simulation work.

- Dorkenwald et al., “Neuronal wiring diagram of an adult brain,” *Nature* 634 (2024).
- Schlegel et al., “Whole-brain annotation and multi-connectome cell typing of
  *Drosophila*,” *Nature* 634 (2024).
- Shiu et al., “A *Drosophila* computational brain model reveals sensorimotor
  processing,” *Nature* 634 (2024). [Paper](https://doi.org/10.1038/s41586-024-07763-9);
  [model code](https://github.com/philshiu/Drosophila_brain_model) (MIT).
- [FlyWire](https://flywire.ai) · [Codex annotation service](https://codex.flywire.ai).

See [source records](docs/sources.md) for provenance.
