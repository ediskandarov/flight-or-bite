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
- Next: wait for the author to report “main done” / “latency done” / “sampled done” -> check line counts (1500 / 500), `stops.jsonl`, commit `reports/online`, `reports/latency` -> `uv run fob report` -> read the whole report once -> commit. Nothing else is owed.

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

## 2026-10-06 — direct TypeSafe probe and cost accounting (D63)

- User requested direct Jev access, added TYPESAFE_API_KEY locally, and reported $5.00 initial balance. Added scripts/jev_direct_probe.py using the official /v1/systemone endpoint and pinned jev-1.13.0. Existing OpenRouter client and frozen files are unchanged.
- One smoke call, then 20 warm-up + 100 measured calls: all 121 succeeded, response model jev-1.13.0 throughout. Exploratory HTTP p50 / p95 294.162 / 384.565 ms. Agent-process preliminary timings; do not attribute the difference from the earlier OpenRouter benchmark solely to routing.
- reports/direct_typesafe contains the sanitized raw requests/responses, summaries, opening balance, spend ledger and explanatory README. Total 89,724 input tokens; estimated cost $0.003768408; estimated balance $4.996231592. Actual provider balance not queried. Shared call ledger 73,403 / 100,000.
- Validation: response choices and probability distributions checked for every successful call; spend arithmetic, aggregation and missing-usage handling checked offline; ruff passed. No key or authorization header is written. Frozen hashes verified before each run.
- Main-project next step remains the 100-episode sampled run from reports/run_instructions.md section 3. Direct results are exploratory and kept outside the primary report data.

## 2026-10-06 — full direct benchmark prepared (D64); awaiting author's run

- Added scripts/jev_direct_bench.py and a separate TypeSafeClient. Reuses the existing JevArbiter and bench_one timers with the frozen timing configuration: four modes, 20 warm-up + 1000 timed calls each. Does not modify the original OpenRouter client or report inputs.
- Direct output: reports/latency_typesafe; OpenRouter remains reports/latency. Guard rejects writing into the reference directory, unknown nonempty outputs and protocol changes during resume. AC/timer checks abort before calls if invalid. Auth/billing/model failures stop; raw response or transport failure is recorded. Resumes preserve completed samples and repeat warm-up only for unfinished modes.
- Shared TypeSafe spend module aggregates both old probe summaries and new raw benchmark logs, including warm-up and failures. The probe now uses it too, avoiding loss of benchmark costs on later probes. Unknown usage suppresses the balance estimate. Project-wide 100000-call cap still applies.
- Validation: 59 offline tests passed (direct API, spend, preserved output, resumption, bad-power stop, bench, original client/arbiter, online); ruff passed. No new API calls made. Frozen hashes and original OpenRouter latency data unchanged.
- Author command: reports/run_instructions.md section 6. Expected 4080 calls, roughly 20–30 minutes, under $0.15 estimated. After completion inspect protocol.json, bench_meta.json, per-mode counts and comparison.md, update actual estimated spend and commit results. Secondary sampled main experiment remains pending (section 3).

## 2026-10-06 — full direct TypeSafe benchmark complete and audited

- Author completed scripts/jev_direct_bench.py, 13:37–13:58 Asia/Tbilisi; all four modes contain 1000 timed decisions plus 20 warm-up calls and one cold-call marker. Total 4080 successful calls, no retries, failures or cache hits. AC power, timer_throttled=false; all responses model jev-1.13.0.
- Audit verified the frozen preregistration, timing configuration and prompt hashes; exact observation/warm-up pairing against every corresponding OpenRouter record; raw response counts, statuses, models and prompts; per-mode state sequence; and positive timings. Existing reports/latency matches commit 7bd714c byte-for-byte. Secret exclusion checked on every saved direct-benchmark file.
- Median direct / OpenRouter ms: naive 305.940 / 322.671; informed 304.822 / 354.686; bucketed 306.684 / 315.353; informed_bucketed 306.541 / 325.308. Informed reduction 14.059%; p95 408.762 vs 479.109 ms. Different run times and unverified snapshot identity prevent attributing the full difference to the routing intermediary.
- Benchmark input tokens 2,277,908; estimated benchmark cost $0.095672136. With the 121-call probe: 4201 calls, 2,367,632 input tokens, estimated total cost $0.099440544, estimated balance $4.900559456 from the reported $5.00. Actual provider balance not queried. Shared project ledger 77,483 / 100,000; 22,517 calls remain.
- Saved raw and per-decision data, protocol, metadata and comparison in reports/latency_typesafe. Updated README and marked initial direct-probe cost figures as historical. Main OpenRouter experiment and report inputs preserved.
- Run metadata records source commit c373cb7 and git_dirty=true: the runner creates the untracked protocol.json before start_run, so its own output already makes the tree dirty. Current source files have no modifications.
- Next: main-study secondary sampled run remains absent. Author runs reports/run_instructions.md section 3 (100 episodes per arbiter, 500 total), then audit and rebuild the complete main report. Additional direct benchmark is already complete and must not be needlessly repeated.

## 2026-10-06 — secondary sampled run audited; final report complete

- Author completed the secondary sampled test from clean commit 1724605, starting at 15:10 Asia/Tbilisi. reports/online/test_sampled contains 500 episodes (100 seeds × five arbiters) and 21,133 decisions. Seeds 100000–100099 are complete and unique; decision order, action totals and episode outcomes match, with no orphan records. Deterministic arbiters match the corresponding main-run episodes.
- Jev: 3,097 decisions, model typesafe/jev-1.13-20260917 throughout; zero retries and stops. Mean lifetime 29.97 vs connectome 24.06; paired difference +5.91, 95% CI [0.63, 11.03025]. This is secondary analysis; the primary comparison remains +31.49 [28.0598, 34.91] from 300 paired episodes.
- Rebuilt and reviewed the complete reports/final_report.md from saved artifacts. Removed the interim state, retained primary OpenRouter measurements and linked the separate direct TypeSafe supplement. Corrected report rendering: numeric retry count, explicit censored share, and no primary-winner declaration for secondary results. Added a regression test for the latter. Scoped the OpenRouter limitation to the main experiment.
- Combined call ledger: 80,580 / 100,000; 19,420 remain. Direct TypeSafe spend unchanged at estimated $0.099440544, estimated balance $4.900559456; actual balance not queried. No new API calls or experiments during report assembly.
- All planned runs are complete. README and run instructions now reflect completion. Original OpenRouter latency data and frozen preregistration remain unchanged. G6 limitation remains: conclusions depend on manually chosen parameters.
- Validation: all 14 frozen hashes match; 4 report tests passed; ruff, report-link checks and git diff --check passed. reports/latency matches commit 7bd714c byte-for-byte.
- Next / waits for author: nothing required for the planned experiment. Preserve completed results; any future experiment must be explicitly separate.

## 2026-10-06 — English documentation edition complete (D65)

- User requested an up-to-date English README and English versions of all reports and documentation. Rewrote README around the completed experiment, primary/secondary outcomes, separate direct API benchmark, limitations, reproduction commands, and spend accounting.
- Translated all remaining non-English repository documentation and historical reports. Updated report generators, table headers, figure labels, and corresponding report assertions; rebuilt the final report, gates report, template report, and final-report figures from saved artifacts only. Updated API notes to distinguish the main OpenRouter client from the separate direct TypeSafe client.
- PREREG and SPEC carry explicit post-experiment translation notices. Original frozen PREREG remains at 4a6f04850036e154f4f87e72e0509a8ff20a33cb; complete pre-translation state at 02b66fc9d1797c3be77a4d9319a4143837bb8f5a. D65 and the final report disclose the editorial change after freezing. The scientific protocol, statistical logic, 14 hashes, prompts, raw results, and original OpenRouter data are unchanged.
- Validation: no Cyrillic remains in tracked text files; numeric content preserved in 832 existing documentation-table rows and all 64 prior decision rows (D65 adds the translation record). All local Markdown links resolve. All eight final-report figures were visually inspected. Python syntax-tree comparison confirmed text-only changes outside the added disclosure. All 14 frozen hashes match; 46 focused offline tests passed; ruff and git diff --check passed.
- No experiments or API requests were run. Project usage remains 80,580 / 100,000; estimated direct TypeSafe spend remains $0.099440544. No remaining task blockers or author actions.
