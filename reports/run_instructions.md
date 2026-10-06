# Author instructions: runs from your own terminal (D5, D59)

**Status as of 2026-10-06: all runs are complete and verified, including the additional direct TypeSafe API benchmark. No rerun is needed. [Final report](final_report.md). Instructions below are retained for reproducibility.**

Date: 2026-09-20. `PREREG.md` was frozen in commit `4a6f048`. Run everything below **from a normal terminal** (Terminal / iTerm), not the agent session: timers are distorted in the agent process. Three runs: **1) main online run → 2) latency benchmark → 3) secondary sampled run**. Runs 1 and 2 may be swapped; run 3 may occur any time after run 1.

## 0. Before each run (1 minute)

```bash
cd ~/workspace/flight-or-bite
pmset -g batt | head -1                      # expected: Now drawing from 'AC Power'
git status --short                           # empty, or only reports/ created by runs
uv run python -c "from flight_or_bite import prereg; prereg.check(); print('PREREG frozen, hashes match')"
pgrep -fl "fob (confirm|table build --arbiter connectome)" || echo "No heavy agent computation; ready to run"
cat runs/jev_ledger.json                     # Jev call usage; limit 100,000
```

- **AC power, lid open**, heavy applications closed (video playback, Docker, builds).
- If `pgrep` returns a process, the agent is still computing H1–H4 or the connectome table, occupying cores and distorting connectome `t_wall`. **Wait for completion** (the agent will report it; usually < 1 h after freezing). Jev table building (`fob table build --arbiter jev …`) is network-bound and uses little CPU; it does not obstruct the main run, but **start the latency benchmark (section 2) only when Jev tables are not being built**: `pgrep -fl "fob table build --arbiter jev" || echo ok`.
- `OPENROUTER_API_KEY` is read from `.env` in the repository root, as before.

## 1. Main online `test` run (PREREG §2) — first access to the test split

```bash
caffeinate -i uv run fob eval --split test --unlock-test --online 2>&1 | tee -a runs/main_test.log
```

- Runs 300 paired episodes, seeds 100000–100299, five arbiters (`connectome`, `jev_informed`, `oracle`, `fixed_priority`, `random`), native actions, no deadline. All arbiters play each seed before proceeding.
- Writes `reports/online/test/episodes.jsonl` (one row per completed episode), `decisions.jsonl` (one row per decision, including `t_wall_ns`, `t_sim_ms`, `retried`), and `stops.jsonl` if stopped; metadata: `runs/<timestamp>_online-test/meta.json`; test access: `runs/test_access.log`; raw Jev responses: `runs/jev_raw/<date>.jsonl`.
- **Expected time: 2–2.5 hours** (approximately 20,000 Jev calls × ~0.4 s; connectome and baselines take minutes). Progress every 10 seeds. Expected Jev usage: approximately 20,000 calls.
- Finishes with mean lifetime and CI table and `300 paired episodes in reports/online/test`.

**If interrupted** (Jev failure under §2b, shown as red `stopped at seed …`; Ctrl-C; sleep; network loss):

1. Do not delete or edit anything. The incomplete episode was not saved and will replay from the beginning on the same seed; completed episodes are retained.
2. Inspect the cause: `tail -1 reports/online/test/stops.jsonl`. HTTP 401/402 indicates an OpenRouter key or balance issue. `JevModelMismatch` means a response outside `jev-1.13`: **do not restart; tell the agent**. For 5xx/network failures, wait a few minutes.
3. Run **the same command** again. It prints `N episode(s) already done` and resumes at the first incomplete episode.
4. Resume identically after Ctrl-C. Every Jev failure stop is recorded in `stops.jsonl` and reported.

After completion:

```bash
wc -l reports/online/test/episodes.jsonl     # 1500 = 300 seeds × 5 arbiters
cat runs/test_access.log
```

## 2. Latency benchmark (PREREG §8, `configs/timing.yaml`)

```bash
pgrep -fl "fob table build --arbiter jev" || echo ok     # expected: ok
caffeinate -i uv run fob latency bench --arbiter all 2>&1 | tee -a runs/latency_bench.log
```

- Measures 1,000 decisions per arbiter. Jev: four state modes sequentially, each with its own keep-alive session and 20 warm-up calls (first is cold, reported separately); caching disabled, **no retries**: failed calls are logged and excluded. Then connectome (one process, graph in memory, separate `t_load`, early stopping), then `oracle`, `fixed_priority`, `random`. States are grid B nodes in a fixed shuffled order.
- Writes `reports/latency/<arbiter>.jsonl` and `reports/latency/bench_meta.json` (power, timer-throttling check, `t_load`).
- **Expected time: approximately 35 minutes** (Jev 4 × 1020 × ~0.4 s ≈ 28 min; connectome ≈ 2–3 min; others take seconds). Expected Jev usage: approximately 4,100 calls.
- Prints `throttle check: {...}` at startup. If the yellow “not on AC power or timers are throttled” warning appears, stop with Ctrl-C, resolve the cause, remove `reports/latency/`, and restart. This historical recovery instruction applies only to an invalid, unfinished benchmark, not the preserved completed results.
- **Resume:** the same command fills each arbiter to 1,000 measurements. A resumed Jev mode repeats warm-up because the new connection is cold; multiple cold calls per mode are therefore possible and will appear in the report.
- If a Jev mode exceeds 5% failures, the table marks it “invalid benchmark”; tell the agent without deleting files.
- View results again: `uv run fob latency show`.

## 3. Secondary run: actions sampled from `probs` (PREREG §2)

```bash
caffeinate -i uv run fob eval --split test --unlock-test --online --sample-from-probs 2>&1 | tee -a runs/sampled_test.log
```

- 100 paired episodes, seeds 100000–100099; writes to `reports/online/test_sampled/`. **Expected time: 30–50 minutes**, approximately 6,500 Jev calls (PREREG §9 estimate). Stop/resume behavior as in section 1.
- Check: `wc -l reports/online/test_sampled/episodes.jsonl` → 500.

## 4. What not to do

- Do not run 1 and 3 concurrently with each other or with benchmark 2.
- Do not change files listed in `PREREG.md` §11: the guard will fail (`preregistered hashes do not match`).
- Do not delete `reports/online/test/*` after a run begins: the confirmatory run is performed once on PREREG seeds. If anything goes wrong, tell the agent first.
- Do not close the laptop lid: `caffeinate -i` does not prevent lid-close sleep without an external display.

## 5. After the runs

Tell the agent “main run done,” “latency done,” or “sampled done.” The agent will commit `reports/online/` and `reports/latency/` and build `fob report`. Jev pass 2 cannot finish earlier than 12 hours after pass 1; the report is assembled afterward. All of these steps are now complete.

## 6. Additional full Jev benchmark directly through TypeSafe (D64)

Requested by the author on 2026-10-06 after the main experiment. An additional comparison,
separate from the frozen primary experiment. Original OpenRouter data remain
in `reports/latency/`; the new series writes to `reports/latency_typesafe/`.

Run in a normal terminal, on AC power, without concurrent experiments or heavy load:

```bash
cd ~/workspace/flight-or-bite
caffeinate -i .venv/bin/python scripts/jev_direct_bench.py 2>&1 | tee -a runs/latency_typesafe.log
```

- Four Jev modes, 1,000 timed requests and 20 warm-up calls each: 4,080 calls total.
  Same mode order, states, templates, and `JevArbiter`/`bench_one` timer as OpenRouter.
  Model pinned to `jev-1.13.0`; requests go only to `https://api.typesafe.ai/v1/systemone`.
- Key from `TYPESAFE_API_KEY` in the environment or `.env`; never logged.
- Estimate: 20–30 minutes; expected spend under $0.15 at $0.042/M input tokens.
  Accounting includes warm-up and resumed runs: `reports/direct_typesafe/spend.json`.
  All attempts also count toward the project-wide 100,000-call limit.
- Power and timer checks are mandatory; a problem stops the script before API calls.
- Repeating the same command resumes missing requests. Completed modes are not rerun.
  Resuming an incomplete mode adds another warm-up, included in spend accounting.
  Resolve HTTP 401/402/403 or model-version mismatch before resuming.
  Do not delete partial results: they contribute to spend and failure accounting.
- `protocol.json` prevents mixing protocols during resume.
  `bench_meta.json` records conditions and status for every run, including interruptions.
- On completion, the comparison appears in `reports/latency_typesafe/comparison.md`.
  It compares p50/p95 for each mode; differences cannot be attributed entirely to OpenRouter:
  runs occurred at different times and provider snapshot identity is unverified.
- The main report continues to use the original OpenRouter benchmark. The additional comparison
  is stored separately; observed results are not used for parameter tuning.

Historical next step after this benchmark was the section 3 secondary experiment; both are now complete.
