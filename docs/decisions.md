# Decisions log

Human decisions that refine or deviate from `SPEC.md`. The spec itself is not edited; where this
file and the spec disagree, this file wins. Each entry: date, decision, rationale, effect.

## 2026-09-19 — end of M0 (all recommendations in `open_questions.md` accepted)

| # | Decision | Effect |
|---|---|---|
| D1 | **Jev stays the main arbiter** (SPEC design unchanged). Reached through OpenRouter's alpha Decisions endpoint, since direct TypeSafe access is invite-only. Gemini 3.7 Flash as an extra "LLM" baseline is optional and deferred | No change to RQ1–RQ5. Jev's `t_wall` includes the OpenRouter hop; the report says so |
| D2 | **`N_rep = 20` for Jev** policy tables — Jev was observed to be non-deterministic | Deviates from SPEC §4.5 (450 calls → 9,000). All repeats are stored; the cache never deduplicates by request bytes. Gives the noise floor for the live-vs-table check (SPEC §7) |
| D3 | OpenRouter's per-generation `latency` is collected **after** timed runs and reported as **`t_gateway`**, never as `t_server` | `Decision.t_server_ms` stays `None` for Jev (SPEC §6.1 unchanged); `t_gateway` is an additional, clearly named column |
| D4 | Connectome version: **783 provisionally**, final choice at M1 after reading the paper and `model.py` | See M1 notes |
| D5 | Decision-grade measurements (backend choice, grid size, `latency bench`) are **re-run by the human** from their own terminal, on AC power, under `caffeinate -i`. The agent's runs are for development. `fob perf` records a throttling self-check | Applies to M1 and M4 |
| D6 | Python **3.12** | — |
| D7 | A third, preregistered Jev state mode **`bucketed`** (numbers → named levels) joins `naive` and `informed`. Bucket boundaries are fixed before any data is seen and go to `ENGINEERED.md` | Deviates from SPEC §4.3 (2 modes → 3). Jev table: 225 × 3 × 20 = 13,500 calls |
| D8 | **`--max-calls` default 100,000** (SPEC: 30,000), counter to persist across runs (due M4) | Money is not the constraint (~$1.40 per 100k calls) |
| D9 | The expected response `model` (`typesafe/jev-1.13-20260917`) is pinned in config and in `PREREG.md` hashes; a different value aborts the run. The alpha status of the endpoint is accepted as a risk and listed under limitations | Due M4 |

## 2026-09-20 — SPEC §6 simplified (human instruction)

| # | Decision | Effect |
|---|---|---|
| D10 | **Time is measured on the client only.** Every arbiter reports `t_wall`; the connectome additionally reports `t_sim`. | `Decision.t_server_ms` is removed. SPEC §6.1 shrinks to two quantities. Analysis 6.3-A is a `t_wall` table (plus `t_sim` and RTF for the connectome) |
| D11 | **Removed from SPEC §4.3 / §6.2:** `t_server`; the connect / first-byte / total breakdown; the 8-parallel-requests throughput test; network metadata (Wi-Fi/cable, city, time of day); any measurement through TypeSafe's direct API | `JevClient` has no trace hooks and no backend switch. **Supersedes D3** (`t_gateway` from OpenRouter's generation metadata is not collected) |
| D12 | **OpenRouter is the main and only access path** to Jev (`POST /api/alpha/decisions`, key `OPENROUTER_API_KEY`) | `JEV_API_KEY` / `TYPESAFE_API_KEY` are no longer read. Jev's `t_wall` includes the OpenRouter hop by design; the report states it. The endpoint's alpha status stays a listed limitation |
| D13 | **Model pinned: `jev-1.13`** — requested as `typesafe/jev-1.13`. OpenRouter answers with a dated snapshot (`typesafe/jev-1.13-20260917` today); any reply from outside the `jev-1.13` family raises `JevModelMismatch` and aborts the run. The exact snapshot id is logged per call | **Refines D9**: the pin is the family, not one dated snapshot; a snapshot change inside the family is recorded, not fatal |
| D14 | Latency is reported as **p50 / p95** (SPEC: p50 / p90 / p99) | `summarize_ns`, `fob jev smoke`, later `fob latency show` and `fob live` |
| D15 | **Kept as in the SPEC:** cache forcibly off in every timed run and `cache_hit = true` never enters latency statistics; chronometric curves (6.3-C); deadline sweep with both tracks (6.3-D); the speed-vs-quality figure (6.3-B) | — |

Not mentioned in the instruction and therefore left as in the SPEC until told otherwise: the
20-call warm-up with the cold first call reported separately; sequential calls over one
keep-alive session; the ECDF figure; the power-source / timer-throttling self-check of `fob perf`
(it describes the machine, not the network).

## 2026-09-20 — M1 accepted

| # | Decision | Effect |
|---|---|---|
| D16 | **M1 accepted. LIF backend: `event`** (NumPy + Numba). Brian2 stays as the reference in the test suite; the PyTorch backends stay as measured and rejected candidates | — |
| D17 | **Connectome: v783** (final; supersedes the provisional D4) | v630 remains downloadable for cross-checks only |
| D18 | Before M2: an **exploratory probe of the looming channel** (`reports/probe_looming.md`), 1–2 hours, nothing tuned, stop after the report. Everything in it is labelled exploratory (SPEC §8) | Not a milestone; does not count as G3 or G7 |
| D19 | Raw Jev responses are logged to disk from now on, before any new call is made | Closes the gap noted in `reports/status.md` §7 |
