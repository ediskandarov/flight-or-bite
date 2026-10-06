"""Exploratory TypeSafe probe; independent of the frozen OpenRouter experiment.

API/model/pricing sources (checked 2026-10-06):
https://docs.typesafe.ai/api and https://docs.typesafe.ai/models
Run from the repository root. Credentials are never logged; no retries or redirects.
"""

import argparse
import json
import math
import os
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import dotenv_values

from flight_or_bite import prereg
from flight_or_bite.arbiters.jev_arbiter import load_prompt, prompt_hash
from flight_or_bite.arbiters.jev_client import CallBudget, build_payload
from flight_or_bite.timing.bench import load_cfg, states
from flight_or_bite.timing.timers import summarize_ns
from flight_or_bite.types import Observation

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
RATE_PER_MILLION = Decimal("0.042")


def update_spend(root):
    """Sum saved probe usage; never present a local estimate as a provider balance."""
    opening_path = root / "opening_balance.json"
    if not opening_path.is_file():
        return
    opening = json.loads(opening_path.read_text())
    summaries = [json.loads(p.read_text()) for p in sorted(root.glob("*/summary.json"))]
    cost = sum((Decimal(s["estimated_known_cost_usd"]) for s in summaries), Decimal(0))
    unknown = sum(s["calls_with_unknown_usage"] for s in summaries)
    ledger = {
        "opening_balance": opening,
        "tracked_attempts": sum(s["attempts"] for s in summaries),
        "known_input_tokens": sum(s["known_input_tokens"] for s in summaries),
        "calls_with_unknown_usage": unknown,
        "estimated_known_spend_usd": str(cost),
        "estimated_balance_usd": str(Decimal(opening["balance_usd"]) - cost) if not unknown else None,
        "actual_current_balance_verified": False,
        "assumptions": "Public per-token prices; no other account usage, credits, taxes or billing adjustments",
    }
    (root / "spend.json").write_text(json.dumps(ledger, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=0)
    args = parser.parse_args()
    if args.n < 1 or args.warmup < 0 or args.n + args.warmup > 120:
        parser.error("Use 1–120 calls total, including warm-up")
    key = os.environ.get("TYPESAFE_API_KEY") or dotenv_values(".env").get("TYPESAFE_API_KEY")
    if not key:
        parser.error("TYPESAFE_API_KEY is missing")
    key = key.strip()
    prereg.check()
    prompt = load_prompt("informed")
    feed = states(load_cfg()["state_seed"])
    budget = CallBudget(100_000, Path("runs/jev_ledger.json"))
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
    out = Path("reports/direct_typesafe") / f"{stamp}_{uuid4().hex[:8]}"
    out.mkdir(parents=True, exist_ok=False)
    records = []
    failure = None
    with httpx.Client(timeout=30.0, follow_redirects=False, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"
    }) as client, (out / "calls.jsonl").open("a") as log:
        for i in range(args.n + args.warmup):
            warmup = i < args.warmup
            obs = Observation(0.5, 0.0, 0.5, 0.5) if warmup else next(feed)
            payload = build_payload(prompt.state(obs), {"action": prompt.question()}, MODEL)
            record = {"index": i, "warmup": warmup, "cold": i == 0,
                      "ts": datetime.now().astimezone().isoformat(), "endpoint": ENDPOINT,
                      "request": json.loads(payload), "ok": False}
            try:
                budget.spend()
                t0 = time.perf_counter_ns()
                response = client.post(ENDPOINT, content=payload)
                record["t_http_ns"] = time.perf_counter_ns() - t0
                record["status"] = response.status_code
                record["response_text"] = response.text.replace(key, "[REDACTED]")
                if response.status_code != 200:
                    raise ValueError(f"HTTP {response.status_code}")
                body = response.json()
                record["model"] = body.get("model")
                record["usage"] = body.get("usage", {})
                if record["model"] != MODEL:
                    raise ValueError("Response model differs from the requested version; inspect logged response")
                answer = body["answers"]["action"]
                probs = answer["probabilities"]
                if (answer.get("type") != "choice" or answer["choice"] not in {"EAT", "ESCAPE", "IDLE"}
                        or set(probs) != {"EAT", "ESCAPE", "IDLE"}
                        or any(not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1
                               for p in probs.values())
                        or abs(sum(probs.values()) - 1) > 0.02):
                    raise ValueError("Invalid choice/probability response")
                record.update(ok=True, choice=answer["choice"], probabilities=probs)
            except Exception as exc:
                failure = f"{type(exc).__name__}: {str(exc)}".replace(key, "[REDACTED]")[:400]
                record["error"] = failure
            log.write(json.dumps(record, ensure_ascii=False).replace(key, "[REDACTED]") + "\n")
            log.flush()
            records.append(record)
            if failure:
                break
    tokens = [r.get("usage", {}).get("input_tokens") for r in records]
    known_tokens = sum(t for t in tokens if isinstance(t, int) and t >= 0)
    unknown = sum(not isinstance(t, int) or t < 0 for t in tokens)
    cost = Decimal(known_tokens) * RATE_PER_MILLION / Decimal(1_000_000)
    measured = [r["t_http_ns"] for r in records if r["ok"] and not r["warmup"]]
    timing = summarize_ns(measured) if measured else None
    summary = {
        "kind": "exploratory_direct_api_probe", "endpoint": ENDPOINT, "requested_model": MODEL,
        "mode": "informed", "prompt_sha256": prompt_hash("informed"),
        "requested_n": args.n, "requested_warmup": args.warmup,
        "attempts": budget.session, "successful": sum(r["ok"] for r in records),
        "timed_successes": len(measured), "cold_http_ms": records[0].get("t_http_ns", 0) / 1e6,
        "http_p50_ms": timing.p50_ms if timing else None, "http_p95_ms": timing.p95_ms if timing else None,
        "error": failure, "known_input_tokens": known_tokens, "calls_with_unknown_usage": unknown,
        "estimated_known_cost_usd": str(cost), "input_usd_per_million": str(RATE_PER_MILLION),
        "output_price_usd": "0", "pricing_source": "https://docs.typesafe.ai/models",
        "budget_calls_used": budget.used,
        "limitations": ["Agent process: preliminary timing, not a D5 benchmark",
                        "HTTP round trip only; existing arbiter timing includes additional local work",
                        "No client response cache; provider-side caching is not verified",
                        "Cost is a public-rate estimate, not a balance inquiry or invoice"],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    update_spend(out.parent)
    print(json.dumps({"output": str(out), **summary}, indent=2))
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
