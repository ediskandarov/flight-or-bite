# Direct TypeSafe API: exploratory probe, 2026-10-06

> Historical results from the first short probe (121 requests).
> The full benchmark (4,080 additional requests) is complete: [OpenRouter comparison](../latency_typesafe/comparison.md).
> Total estimated direct-test spend: $0.099440544; estimated remaining balance: $4.900559456.
> Current aggregate accounting: [spend.json](spend.json); the account balance has not been verified.

The user requested this probe after the main OpenRouter experiment.
Endpoint: `https://api.typesafe.ai/v1/systemone`; requested and returned
model: `jev-1.13.0`. Used the unchanged `informed` v1 template.

Sources: [API](https://docs.typesafe.ai/api), [models and pricing](https://docs.typesafe.ai/models),
checked 2026-10-06. Price: $0.042 per million input tokens; output is free.

## Result

- Initial probe: 1 successful request, 741 input tokens, 310.9 ms (cold connection).
- Short series: 20 warm-up + 100 timed requests, all 120 successful.
- Series states: the first 100 points in the same fixed grid B sequence
  used by the protocol benchmark; warm-up state (0.5, 0, 0.5, 0.5).
- One keep-alive HTTP session per run; no retries or client-side cache.
- HTTP p50: **294.162 ms**; p95: **384.565 ms**. Series cold request: 316.666 ms.
- Total: 121 requests, **89,724 input tokens**. No missing usage records.

## Spend

The **$5.00** opening balance was reported by the user, not returned by a balance API.
Estimated spend: **$0.003768408**. Estimated remaining balance: **$4.996231592**.
These are estimates from published pricing, not verified charges; other account activity,
credits, rounding, and billing adjustments are excluded.

Accounting: `opening_balance.json`, `spend.json`; each run retains `calls.jsonl`
and `summary.json`. After each run the script recomputes aggregate spend from saved
summaries; unknown usage suppresses the balance estimate. Keys and authorization
headers are not saved. Attempts also count toward the project limit: 73,403 / 100,000 at this stage.

## Comparison limitations

This is an additional probe from the agent's process, not a D5 benchmark or part of
the frozen primary comparison. The original OpenRouter informed benchmark measured
p50 354.686 ms and p95 479.109 ms across 1,000 states. This direct probe has
100 timed states, was run at a different time, and measures only the HTTP exchange,
whereas the main arbiter includes additional local processing.
Snapshot identity between `jev-1.13.0` and `typesafe/jev-1.13-20260917` is unverified.
Provider-side caching was not checked. The difference therefore cannot be attributed
entirely to removing OpenRouter or treated as a controlled acceleration estimate.

For reproducibility only (the probe is complete), the short-series terminal command from the repository root is:

```bash
caffeinate -i .venv/bin/python scripts/jev_direct_probe.py --n 100 --warmup 20
```

Repeating it makes 120 additional paid calls; each new series is saved in a separate directory.
The main OpenRouter client, preregistered protocol, and frozen configurations were unchanged by these probes.
