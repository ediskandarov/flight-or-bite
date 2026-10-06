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

## 2026-10-05 — project resumed; readiness audit and run-log collision fixed

- Restored state from PREREG, decisions and this handoff (README and open_questions still described M3). Verified the frozen preregistration and all 14 hashes. Confirmatory results are present; they were not rerun.
- Checked parquet metadata: connectome 24,500 rows; each of four Jev modes 12,250 rows; all sessions contain 49 shards. Each Jev pass-2 start is at least 12 h after its pass-1 finish. Ledger remains 52,285 / 100,000.
- Still absent: reports/online/test/episodes.jsonl, reports/online/test_sampled/episodes.jsonl, reports/latency/, runs/test_access.log. No new live API calls or experiments were made.
- Readiness tests exposed a runlog bug: resuming within the same second raised FileExistsError before the runner could resume. start_run now atomically creates a separate suffixed directory on a name collision, preserving prior metadata. A regression test holds the clock fixed and verifies three independent metadata records.
- Updated README and marked open_questions as a historical log. Frozen files, scientific parameters, hypotheses and existing results are unchanged.
- Validation: 46 tests passed (runlog, online, bench, report, Jev client, policy table); ruff and git diff --check passed; prereg.check() passed after the fix. Tests used mock Jev and temporary outputs only.
- Next: the author runs the three commands in reports/run_instructions.md from their terminal (D59), starting with the main online test run. Then validate outputs and build the final report from artifacts. Current API availability and balance have not been checked.

## 2026-10-06 — main online test run complete and audited

- Author ran the preregistered main command from their terminal, 11:02–12:44 Asia/Tbilisi, starting from clean commit d8ae502. Results: reports/online/test/episodes.jsonl (1,500 records) and decisions.jsonl (68,671 records). All five arbiters have exactly seeds 100000–100299, with no duplicate or missing episode keys. Decision counts, trial ordering and action totals match every episode; no orphan decision groups.
- Jev: 16,917 decisions, all model typesafe/jev-1.13-20260917, no retries, no stops. Ledger 69,202 / 100,000; 30,798 calls remain. Frozen preregistration hashes still match.
- Main preregistered comparison: Jev informed lifetime 55.39 vs connectome 23.90 trials; paired difference +31.49, bootstrap 95% CI [28.0598, 34.91]. Jev wins this specified comparison. Fixed priority averages 56.6633; its descriptive difference from Jev (+1.2733, CI [-3.3236, 5.8734]) is not significant. These are survival results in the specified environment, not a general intelligence ranking.
- Rebuilt reports/final_report.md and figures from artifacts only. Report remains explicitly INTERIM: latency bench and the secondary sampled run are absent. No new API calls or simulations. README updated.
- Next: author runs reports/run_instructions.md section 2 (latency bench) on AC power, then section 3 (100 sampled episodes). Preserve main results; do not rerun or tune parameters based on them. After both outputs arrive, audit and rebuild the complete report.

## 2026-10-06 — protocol latency benchmark complete and audited

- Author ran fob latency bench --arbiter all from their terminal, 12:53–13:18 Asia/Tbilisi, starting from clean commit 8a2c53f. reports/latency contains all eight arbiter files and bench_meta.json. One run, mock=false, AC Power, timer_throttled=false; connectome graph load 0.4655 s.
- Audit: exactly 1,000 timed decisions per arbiter; each Jev mode has 20 warm-up calls and one cold-call marker. All timed observations match the fixed state sequence from configs/timing.yaml. No failures, retries, cache hits or nonpositive wall times. All Jev responses use typesafe/jev-1.13-20260917. All 14 preregistration hashes still match.
- Wall latency p50 / p95: connectome 54.424 / 262.922 ms; Jev informed 354.686 / 479.109 ms. Ratio of medians 6.517. These are local runtime versus network-inclusive API latency, not intrinsic model speeds. Connectome t_sim p50 / p95: 187.4 / 500 ms (reported separately).
- Ledger 73,282 / 100,000 after exactly 4,080 additional Jev calls; 26,718 remain. Rebuilt the intermediate report from saved artifacts only; only the secondary sampled run is missing.
- Next: author runs reports/run_instructions.md section 3 (100 paired episodes with --sample-from-probs). Expected 500 episode records. Then audit, rebuild and review the complete final report. No main or latency rerun is needed.
