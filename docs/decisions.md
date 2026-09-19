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
