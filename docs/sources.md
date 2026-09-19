# Sources

Primary sources for everything that SPEC rule 2 forbids inventing: neuron identifiers, model
parameters, the Jev API. Each entry records what it is used for, its licence, and when it was last
checked. "Reachable" means the URL answered HTTP 200 on the check date; it does **not** mean the
content has been read — see the *Read?* column.

Checked: **2026-09-19**.

## Connectome model

| Source | Used for | Licence | Read? |
|---|---|---|---|
| Shiu et al., "A *Drosophila* computational brain model reveals sensorimotor processing", *Nature* 2024. https://doi.org/10.1038/s41586-024-07763-9 | LIF model definition, neuron parameters, the single global weight constant, validation experiments (sugar → MN9) | paper | reachable; **to read at M1** |
| https://github.com/philshiu/Drosophila_brain_model, pinned at commit `91bdd1e7dc` | Reference Brian2 implementation, connectivity files, parameter values, sugar GRN and MN9 ids | MIT (code) | **read in full at M1** (`model.py`, `utils.py`, `example.ipynb`, `Readme.md`); see [lif_model_notes.md](lif_model_notes.md). `figures.ipynb` not read |
| https://github.com/eonsystemspbc/fly-brain (last push 2026-08-29) | Ports to other backends (Brian2, Brian2CUDA, PyTorch, NEST GPU) — cross-checking our non-reference backends. CUDA parts are out of scope | GPL-2.0 | description only |
| FlyWire https://flywire.ai · Codex https://codex.flywire.ai | Cell-type annotations → neuron ids for `data/circuits.yaml` (sugar / bitter GRNs, LPLC2, LC4, MN9, DNp01), each with a `provenance` field | **CC BY-NC 4.0** (data) | reachable; **to use at M1/M3** |

Files in the Shiu repository (from the GitHub tree API):

| File | Size |
|---|---|
| `Connectivity_783.parquet` | 100.8 MB |
| `Completeness_783.csv` | 3.3 MB |
| `2023_03_23_connectivity_630_final.parquet` | 86.6 MB |
| `2023_03_23_completeness_630_final.csv` | 3.1 MB |
| `model.py`, `utils.py`, `example.ipynb`, `figures.ipynb`, `sez_neurons.pickle`, `environment*.yml` | small |

Two connectome versions ship side by side (FlyWire materialisations 630 and 783). Which one the
project uses is an open question for M1 — root ids differ between materialisations, so the choice
fixes every identifier in `data/circuits.yaml`.

**Licence consequence.** FlyWire-derived data is CC BY-NC 4.0: it is downloaded by
`fob fetch-data`, git-ignored, never committed, and the project is non-commercial. The
connectivity files are redistributed inside an MIT-licensed repository; we treat them under the
FlyWire terms regardless. The exact attribution wording required by FlyWire is to be confirmed at
M1 when the data is first fetched; `README.md` carries the citations meanwhile.

## Jev (TypeSafe AI)

Fully read at M0; details and per-claim citations in [jev_api_notes.md](jev_api_notes.md).

| Source | Used for |
|---|---|
| https://docs.typesafe.ai/ (index: `/llms.txt`, full export: `/llms-full.txt`) | Authoritative HTTP reference, models, limits, SDK behaviour, known weaknesses |
| https://developers.cloudflare.com/ai/models/typesafe/jev/ (+ raw JSON schemas) | Alternative access path; machine-readable request/response schema |
| https://typesafe.ai/blog/introducing-system-one-models-and-jev | Positioning, speed and price claims (context only; not tested here, SPEC §6.1) |
| https://openrouter.ai/docs (index `/docs/llms.txt`): Decisions alpha endpoint, generation metadata, response caching, provider routing, latency guide; model catalogue `GET /api/v1/models` | **The access path we actually use** (Jev as `typesafe/jev-1.13`); facts about `google/gemini-3.7-flash` for the open question on an LLM baseline |
| https://www.langchain.com/blog/building-a-harness-with-jev | LangChain integration (`langchain-typesafe`); not used |
| https://github.com/typesafe-ai/system-one-adapter-python (MIT) | "Drop-in TypeSafeClient replacement backed by LLM APIs"; not used — noted because it could serve as an LLM baseline, which is **out of scope** unless the human asks |

## Methodology and related work

| Source | Used for | Read? |
|---|---|---|
| https://www.neuroai.science/p/are-flies-playing-beat-saber | Methodological critique of "connectome plays a game" demos. **SPEC requires reading before M3** | reachable; to read before M3 |
| https://github.com/webergithub/fruitfly-lab (no licence file; last push 2026-09-15) | Example of scrambled-wiring and lesion controls (cf. G4, G5). No licence → read for ideas only, **copy no code** | description only |
| https://github.com/cobanov/awesome-fly (CC0-1.0) | Catalogue of connectome projects, including Apple MPS runs — leads for the M1 backend comparison | description only |

## Tooling facts established on the target machine (2026-09-19)

Not literature, but findings other milestones depend on:

- Apple M3 Pro, 6 performance + 6 efficiency cores, 36 GB RAM, macOS (Darwin 24.6.0), `uv` 0.10.11.
- Project Python pinned to 3.12 (`.python-version`); system Python is 3.14.2. 3.12 was chosen for
  wheel availability of Brian2 / Numba / PyTorch on arm64 — to be confirmed when they are added at M1.
- `time.sleep()` is unreliable for known delays in a process launched by the coding agent:
  `sleep(10 ms)` took a median of ~104 ms, max ~109 ms (overshoot capped at ~100 ms — the
  signature of macOS timer coalescing for throttled processes). A busy-wait on
  `perf_counter_ns()` overshoots by < 30 µs. Consequences: `MockJevClient` busy-waits, and real
  latency benchmarks (SPEC §6.2) must be launched from the human's own terminal.
