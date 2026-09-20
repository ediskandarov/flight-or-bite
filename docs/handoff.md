# Handoff log

Newest entry last. After every finished step: what was done, where the artefacts are, what is next,
what waits for the author. Committed together with the step.

## 2026-09-20 18:18 — state restored after the context overflow; PREREG frozen

- Done: step (a) smoke on dev (`runs/online_smoke/`, 25/25 episodes, was already finished by the previous session); uncommitted work split into `7fcdf8b` (format only) and `799fc0f` (online runner, `validation/confirm.py`, Jev table sessions); new: `fob latency bench/show` (`timing/bench.py`), `fob confirm`, `fob confirm-h5` (`validation/confirm_h5.py`), all crash-tested offline (mock Jev, seeds shifted by +50 000 000; `runs/confirm_smoke/`). Tests no longer write into `runs/`.
- Step (b) done: `PREREG.md` is `Status: FROZEN`, 14 hashes match (`prereg.check()` passes). Decisions D58-D62.
- Jev ledger: 9 343 of 100 000. No access to `test` so far (`runs/test_access.log` does not exist).
- A leftover `git stash` entry ("wip before format split") is a redundant copy of `799fc0f`; safe to drop.
- Next: (c) `reports/run_instructions.md`; (d) `fob confirm`, connectome table; (e) Jev tables pass 1, `fob confirm-h5`; pass 2 not earlier than 12 h after pass 1 ends; (f) `fob report` (still a stub - to be written).
- Waits for the author: nothing blocks. Open to reversal: D60-D62.

## 2026-09-20 18:30 — run instructions written, report code written, long jobs started

- Done: (c) `reports/run_instructions.md` (main test run, latency bench, sampled run; resume = same command). `fob report` implemented (`src/flight_or_bite/report/`: `analyses.py`, `figures.py`, `build.py`), dry-run on smoke artefacts only; the readings where PREREG is silent are listed in `analyses.READINGS` and were committed (`21d7695`) before any table or test result was seen. Call ledger and raw log are now safe for concurrent processes.
- Running in the background (agent's process): `fob confirm` (started 18:18, log `runs/confirm.log`, result -> `reports/confirm/confirm.json`); Jev tables pass 1, modes in the order informed, naive, informed_bucketed, bucketed (started 18:21, log `runs/jev_tables_pass1.log`, ~2.5 h, -> `reports/tables/jev_*/session_1/`); connectome table (started 18:28, log `runs/connectome_table.log`, -> `reports/tables/connectome/`).
- If a job was interrupted: `fob table build ...` resumes by itself (same command; complete shards are kept). `fob confirm` keeps no partial state: re-run the same command - the seeds are fixed by `configs/confirm.yaml`, so the result is the same run, not a second one. It refuses to run once `reports/confirm/confirm.json` exists.
- Next: when `fob confirm` ends - commit `reports/confirm/confirm.json`; then `fob confirm-h5` (440 Jev calls) after the informed table is finished (so that the agent's own Jev calls do not overlap); pass 2 of every Jev table not earlier than 12 h after that table's `session_1/session.json` `finished` time: `uv run fob table build --arbiter jev --mode <mode> --session 2`; then `uv run fob report`.
- Waits for the author: the three runs of `reports/run_instructions.md`. CPU-heavy agent jobs (`fob confirm`, connectome table) must be finished before the author starts - check with the `pgrep` line of the instructions.
