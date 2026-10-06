"""Estimated direct TypeSafe spend, including probes, warm-up and failed attempts."""

import json
from decimal import Decimal
from pathlib import Path

RATE = Decimal("0.042")  # USD / million input tokens; docs.typesafe.ai/models, 2026-10-06


def update_spend(root=Path("reports/direct_typesafe"), bench_root=Path("reports/latency_typesafe")):
    opening_path = root / "opening_balance.json"
    if not opening_path.is_file():
        return None
    opening = json.loads(opening_path.read_text())
    summaries = [json.loads(p.read_text()) for p in sorted(root.glob("*/summary.json"))]
    cost = sum((Decimal(s["estimated_known_cost_usd"]) for s in summaries), Decimal(0))
    tokens = sum(s["known_input_tokens"] for s in summaries)
    unknown = sum(s["calls_with_unknown_usage"] for s in summaries)
    attempts = sum(s["attempts"] for s in summaries)
    for path in sorted(bench_root.glob("raw/*/*.jsonl")):
        for line in path.read_text().splitlines():
            record = json.loads(line)
            attempts += 1
            try:
                usage = json.loads(record.get("response_text", ""))["usage"]["input_tokens"]
                if type(usage) is not int or usage < 0:
                    raise ValueError("invalid usage")
            except (ValueError, KeyError, TypeError):
                unknown += 1
                continue
            tokens += usage
            cost += Decimal(usage) * RATE / Decimal(1_000_000)
    ledger = {"opening_balance": opening, "tracked_attempts": attempts, "known_input_tokens": tokens,
              "calls_with_unknown_usage": unknown, "estimated_known_spend_usd": str(cost),
              "estimated_balance_usd": str(Decimal(opening["balance_usd"]) - cost) if not unknown else None,
              "actual_current_balance_verified": False, "input_usd_per_million": str(RATE),
              "pricing_source": "https://docs.typesafe.ai/models", "pricing_checked_date": "2026-10-06",
              "assumptions": "Public per-token prices; no other account usage, credits, taxes or billing adjustments"}
    target = root / "spend.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2) + "\n")
    tmp.replace(target)
    return ledger
