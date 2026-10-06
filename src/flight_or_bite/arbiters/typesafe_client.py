"""Direct TypeSafe access for the additional comparison authorized by D63/D64.

Official API/model: https://docs.typesafe.ai/api, https://docs.typesafe.ai/models.
The original OpenRouter client remains unchanged.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import httpx

from flight_or_bite.arbiters import jev_client as jev

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"


class TypeSafeClient:
    def __init__(self, api_key=None, *, log_dir: Path, ledger=None, transport=None):
        self._key = (api_key or os.environ.get("TYPESAFE_API_KEY") or "").strip()
        if not self._key:
            raise jev.JevAuthError("TYPESAFE_API_KEY is missing")
        self.budget = jev.CallBudget(jev.DEFAULT_MAX_CALLS, ledger or jev.DEFAULT_LEDGER)
        self.raw_log = jev.RawLog(log_dir)
        self._http = httpx.Client(timeout=jev.DEFAULT_TIMEOUT_S, transport=transport, follow_redirects=False,
                                  headers={"Authorization": f"Bearer {self._key}",
                                           "Content-Type": "application/json"})

    def evaluate(self, state, questions):
        payload = jev.build_payload(state, questions, MODEL)
        self.budget.spend()
        record = {"ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                  "call": self.budget.used, "session_call": self.budget.session, "endpoint": ENDPOINT,
                  "cache_hit": False, "request_bytes": len(payload), "request": json.loads(payload)}
        t0 = time.perf_counter_ns()
        try:
            response = self._http.post(ENDPOINT, content=payload)
        except httpx.TransportError as exc:
            record.update(t_wall_ns=time.perf_counter_ns() - t0, status=None, error=type(exc).__name__)
            self.raw_log.write(record)
            raise
        elapsed = time.perf_counter_ns() - t0
        text = response.text.replace(self._key, "[REDACTED]")
        record.update(status=response.status_code, t_wall_ns=elapsed, response_text=text)
        self.raw_log.write(record)
        if response.status_code in (401, 402, 403):
            raise jev.JevAuthError(f"TypeSafe HTTP {response.status_code}; check account access/balance")
        if response.status_code != 200:
            raise jev.JevHTTPError(response.status_code, text, None)
        try:
            raw = json.loads(text)
        except ValueError as exc:
            raise jev.JevResponseError("TypeSafe response is not JSON; see raw log") from exc
        model, answers, usage = jev._parse_body(raw)
        if model != MODEL:
            raise jev.JevModelMismatch(f"Requested {MODEL}, received {model}")
        return jev.JevResponse(model=model, answers=answers, usage=usage, raw=raw,
                               t_wall_ns=elapsed, request_bytes=len(payload),
                               meta={"backend": "typesafe-direct", "requested_model": MODEL})

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
