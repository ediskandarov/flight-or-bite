# Jev: OpenRouter vs direct TypeSafe (additional analysis)

Direct collection complete: True. Updated 2026-10-06T13:58:56+04:00.
Same prompt versions, state sequence, warm-up and JevArbiter timer; different run times.
Both times include network. Snapshot identity across provider model IDs is not verified.
The original preregistered experiment is unchanged; this comparison was requested after its results.

| Mode | OpenRouter n | direct n | OpenRouter p50 / p95 ms | direct p50 / p95 ms | direct valid (errors) |
|---|---:|---:|---:|---:|---|
| naive | 1000 | 1000 | 322.671 / 420.820 | 305.940 / 408.381 | True |
| informed | 1000 | 1000 | 354.686 / 479.109 | 304.822 / 408.762 | True |
| bucketed | 1000 | 1000 | 315.353 / 438.022 | 306.684 / 410.278 | True |
| informed_bucketed | 1000 | 1000 | 325.308 / 430.739 | 306.541 / 409.775 | True |

Power/timer checks and individual run records: `bench_meta.json`.
Cost estimate (including warm-up, probes and failed attempts): `../direct_typesafe/spend.json`.
