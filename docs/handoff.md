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

## 2026-09-20 18:47 — confirmatory analyses done (step d, part 1)

- Done: `fob confirm` finished (18:18-18:46). `reports/confirm/confirm.json`, run dir `runs/20260920T181855_confirm`, commit `4dfcb44`. By the PREREG criteria: H1, H2, H3, H4, H6 (primary test) confirmed; min Holm p: 2.2e-11, 3e-05, 3.5e-10, 1.1e-11, 1.6e-08. Robustness of H1: sign kept in 7 of 8 variants; variant 3 (`w_syn x1.5`) not: b/c = 0/2, 0/0, 0/0, DNp01 spikes in 95-100 of 100 trials in both arms. Reported as is. Do NOT re-run `fob confirm` (it refuses anyway).
- Still running: connectome table (24 of 49 shards at 18:47), Jev tables pass 1 (informed 32 of 49 shards; ledger 13 376).
- Next: H5 after the informed table ends; pass 2 after 12 h; `fob report`.

## 2026-09-20 19:12 — connectome table and H5 done; the CPU is free for the author's runs

- Done: connectome table `reports/tables/connectome/` (24 500 rows, 18:28-19:05, commit `a4ab2bc`). H5 (`fob confirm-h5`, 19:05-19:11): `reports/confirm/h5.json`, raw answers `reports/confirm/h5_jev.jsonl` (440, no retries, model `typesafe/jev-1.13-20260917`). Delta_Jev = -0.1181 [-0.1226, -0.1137] -> H5 confirmed (CI excludes zero); Delta_oracle = -0.0909; Delta_connectome = -0.4773 [-0.5068, -0.4477]. Do NOT re-run (it refuses anyway).
- Still running: Jev tables pass 1 (network only). `informed` finished 19:00:36 -> its pass 2 may start from 07:01 on 2026-09-21; the other modes 12 h after their own `session_1/session.json` `finished`.
- No CPU-heavy agent job is left. The author may start `reports/run_instructions.md` section 1.
- Next for the agent: wait for pass 1 to end -> commit tables; after 12 h pass 2 (`--session 2`, four modes); when the author's three runs are in - commit `reports/online/`, `reports/latency/`; then `uv run fob report`, read it through, commit.

## 2026-09-20 20:45 — Jev tables pass 1 done (step e, part 1); pass 2 scheduled

- Done: pass 1 of all four Jev tables, `reports/tables/jev_*/session_1/` (commit `b3425c1`): 21 250 calls, 0 retried, model `typesafe/jev-1.13-20260917` everywhere. Ledger 31 033 = 9 343 + 21 250 + 440 (H5). Pass 1 finished: informed 19:00:36, naive 19:41:44, informed_bucketed 20:11:42, bucketed 20:40:57.
- Pass 2 is scheduled: `runs/jev_pass2.sh` runs in the background of the agent's session under `caffeinate -i`, log `runs/jev_tables_pass2.log`. It retries every 10 min while `fob table build ... --session 2` answers "too early" (exit 3), then builds informed, naive, informed_bucketed, bucketed in turn (expected 07:01-09:30 on 2026-09-21). On a Jev failure it stops with `FAILED`; tables are resumable.
- **If the agent's session died overnight**: just run `caffeinate -i ./runs/jev_pass2.sh` again (from any terminal) - finished shards are kept, the 12 h guard is enforced by the code.
- The author had not started the test runs by 20:41 (`reports/online/` absent, `runs/test_access.log` absent).
- Next: after pass 2 -> commit `reports/tables`; after the author's runs -> commit `reports/online`, `reports/latency`; then `uv run fob report`, read it through, commit. Remember: the author's latency bench must not overlap with pass 2 (instructions §2 say so).

## 2026-09-21 09:30 — Jev tables pass 2 done (step e complete); interim report builds on real tables

- Done: pass 2 of the four Jev tables, 07:07-09:22, gap >= 12 h for every mode; `reports/tables/jev_*/session_2/` (commit `a4fc549`). 21 252 attempts: two `naive` calls needed one retry each (flagged `retried`, excluded from latency). Model `typesafe/jev-1.13-20260917` everywhere. Ledger 52 285 of 100 000.
- `uv run fob report` works on the real tables + confirm + H5: `reports/final_report.md` is an INTERIM version (its header says which artefacts are missing).
- The author had not started any of the three runs by 09:22 on 2026-09-21: `reports/online/`, `reports/latency/`, `runs/test_access.log` do not exist. Remaining budget need: ~20 000 + ~6 500 + ~4 100 calls; 47 715 left - enough.
- Next: wait for the author's "главный готов" / "латентность готова" / "sampled готов" -> check line counts (1500 / 500), `stops.jsonl`, commit `reports/online`, `reports/latency` -> `uv run fob report` -> read the whole report once -> commit. Nothing else is owed.
