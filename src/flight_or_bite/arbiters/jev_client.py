"""Jev clients: real HTTP client and a mock with configurable latency (SPEC §4.3, decision D10).

Jev is reached through OpenRouter's alpha Decisions endpoint — the project's only access path.
The wire format is documented in docs/jev_api_notes.md. Time is measured on the client only:
one `t_wall_ns` per call. No SDK is used: a default retry policy would hide several network
round trips inside one "call" and contaminate latency measurements.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import numpy as np

from flight_or_bite.timing.timers import busy_wait_ns

# https://openrouter.ai/docs/api/api-reference/alphadecisions/
BASE_URL = "https://openrouter.ai"
DECISIONS_PATH = "/api/alpha/decisions"
API_KEY_ENV = "OPENROUTER_API_KEY"
GENERATION_ID_HEADER = "x-generation-id"

# Pinned model (D10). OpenRouter answers with a dated snapshot id, e.g. typesafe/jev-1.13-20260917;
# anything outside the jev-1.13 family aborts the run instead of silently mixing models.
MODEL = "typesafe/jev-1.13"

# OpenRouter's response cache is opt-in and does not list this endpoint; the header states our
# intent regardless, so a timed call can never be served from a cache.
NO_CACHE_HEADERS = {"X-OpenRouter-Cache": "false"}

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_CALLS = 100_000  # SPEC §4.3 says 30 000; raised by decision D8 (docs/decisions.md)

State = str | Mapping[str, Any] | list[Any]


class JevError(Exception):
    pass


class JevAuthError(JevError):
    pass


class CallBudgetExceeded(JevError):
    pass


class JevHTTPError(JevError):
    def __init__(self, status: int, body: str, request_id: str | None) -> None:
        super().__init__(f"Jev API returned HTTP {status} (request_id={request_id}): {body[:500]}")
        self.status = status
        self.body = body
        self.request_id = request_id


class JevResponseError(JevError):
    """The response body does not match the documented schema."""


class JevModelMismatch(JevError):
    """The response came from a model outside the pinned family."""


def is_pinned_model(reported: str, pinned: str = MODEL) -> bool:
    return reported == pinned or reported.startswith(pinned + "-")


class CallBudget:
    """The --max-calls fuse. Counts attempts, not successes: a failed call still costs."""

    def __init__(self, max_calls: int = DEFAULT_MAX_CALLS) -> None:
        if max_calls < 0:
            raise ValueError("max_calls must be >= 0")
        self.max_calls = max_calls
        self.used = 0

    def spend(self) -> None:
        if self.used >= self.max_calls:
            raise CallBudgetExceeded(f"call budget exhausted: {self.used}/{self.max_calls}")
        self.used += 1


@dataclass(frozen=True)
class ChoiceQuestion:
    """A Choice question. criteria maps option -> rubric description (None = no detail)."""

    instructions: str
    criteria: Mapping[str, str | None]

    def to_wire(self) -> dict[str, Any]:
        return {
            "type": "choice",
            "instructions": self.instructions,
            "criteria": dict(self.criteria),
        }


@dataclass(frozen=True)
class ChoiceAnswer:
    choice: str
    probabilities: dict[str, float]
    confidence: float


@dataclass(frozen=True)
class JevResponse:
    model: str  # as reported by the server
    answers: dict[str, Any]
    usage: dict[str, Any]
    raw: dict[str, Any]
    t_wall_ns: int  # client-side wall clock of the HTTP exchange; the only time we measure
    request_bytes: int
    request_id: str | None = None
    cache_hit: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def choice(self, question_id: str) -> ChoiceAnswer:
        try:
            ans = self.answers[question_id]
        except KeyError as e:
            raise JevResponseError(f"no answer for question {question_id!r}") from e
        if ans.get("type") != "choice":
            raise JevResponseError(f"answer {question_id!r} has type {ans.get('type')!r}")
        try:
            return ChoiceAnswer(
                choice=str(ans["choice"]),
                probabilities={str(k): float(v) for k, v in ans["probabilities"].items()},
                confidence=float(ans["confidence"]),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            raise JevResponseError(f"malformed choice answer {question_id!r}: {ans!r}") from e


class JevClientProtocol(Protocol):
    budget: CallBudget

    def evaluate(self, state: State, questions: Mapping[str, ChoiceQuestion]) -> JevResponse: ...

    def close(self) -> None: ...


def build_payload(state: State, questions: Mapping[str, ChoiceQuestion], model: str) -> bytes:
    """Serialize a request body. Key order is stable so the bytes can serve as a cache key."""
    if not questions:
        raise ValueError("at least one question is required")
    body = {
        "state": state,
        "model": model,
        "questions": {qid: q.to_wire() for qid, q in questions.items()},
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _parse_body(data: Any) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if not isinstance(data, dict):
        raise JevResponseError(f"response is not a JSON object: {data!r}")
    try:
        model, answers, usage = data["model"], data["answers"], data["usage"]
    except KeyError as e:
        raise JevResponseError(f"response is missing required field {e}") from e
    if not isinstance(model, str) or not isinstance(answers, dict) or not isinstance(usage, dict):
        raise JevResponseError(f"response fields have unexpected types: {data!r}")
    return model, answers, usage


class JevClient:
    """Jev over one keep-alive session. No retries, no cache, pinned model."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_calls: int = DEFAULT_MAX_CALLS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        api_key = api_key or os.environ.get(API_KEY_ENV)
        if not api_key:
            raise JevAuthError(f"no API key: set {API_KEY_ENV} (environment or .env)")
        self.model = MODEL
        self.budget = CallBudget(max_calls)
        self._http = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout_s,
            transport=transport,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                **NO_CACHE_HEADERS,
            },
        )

    def evaluate(self, state: State, questions: Mapping[str, ChoiceQuestion]) -> JevResponse:
        payload = build_payload(state, questions, self.model)
        self.budget.spend()
        t0 = time.perf_counter_ns()
        resp = self._http.post(DECISIONS_PATH, content=payload)
        t_wall_ns = time.perf_counter_ns() - t0

        request_id = resp.headers.get(GENERATION_ID_HEADER)
        if resp.status_code != 200:
            raise JevHTTPError(resp.status_code, resp.text, request_id)
        try:
            raw = resp.json()
        except ValueError as e:
            raise JevResponseError(f"response is not JSON: {resp.text[:500]}") from e
        model, answers, usage = _parse_body(raw)
        if not is_pinned_model(model):
            raise JevModelMismatch(f"pinned {MODEL!r}, but the response came from {model!r}")
        return JevResponse(
            model=model,
            answers=answers,
            usage=usage,
            raw=raw,
            t_wall_ns=t_wall_ns,
            request_bytes=len(payload),
            request_id=request_id,
            meta={
                "backend": "openrouter-decisions",
                "requested_model": self.model,
                "provider": raw.get("provider"),
                "cost_usd": usage.get("cost"),
            },
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> JevClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


ProbsFn = Callable[[State, ChoiceQuestion], Mapping[str, float]]
LatencyFn = Callable[[np.random.Generator], float]


def uniform_probs(state: State, question: ChoiceQuestion) -> dict[str, float]:
    n = len(question.criteria)
    return {option: 1.0 / n for option in question.criteria}


class MockJevClient:
    """Offline stand-in for JevClient returning documented-shape responses.

    latency_s is a fixed delay in seconds, or a callable drawing one from the seeded RNG.
    The delay really elapses (busy-wait), so timers measuring a mock call see a known time.
    """

    MODEL = "mock-jev-0"

    def __init__(
        self,
        *,
        latency_s: float | LatencyFn = 0.0,
        probs_fn: ProbsFn = uniform_probs,
        seed: int = 0,
        max_calls: int = DEFAULT_MAX_CALLS,
    ) -> None:
        self._latency = latency_s
        self._probs_fn = probs_fn
        self._rng = np.random.default_rng(seed)
        self.budget = CallBudget(max_calls)

    def evaluate(self, state: State, questions: Mapping[str, ChoiceQuestion]) -> JevResponse:
        payload = build_payload(state, questions, self.MODEL)
        self.budget.spend()
        t0 = time.perf_counter_ns()
        delay = self._latency(self._rng) if callable(self._latency) else self._latency
        if delay > 0:
            busy_wait_ns(int(delay * 1e9))
        answers = {qid: self._answer(state, q) for qid, q in questions.items()}
        raw = {
            "model": self.MODEL,
            "answers": answers,
            "usage": {"input_tokens": len(payload) // 4, "output_tokens": 0},
        }
        t_wall_ns = time.perf_counter_ns() - t0
        return JevResponse(
            model=self.MODEL,
            answers=answers,
            usage=raw["usage"],
            raw=raw,
            t_wall_ns=t_wall_ns,
            request_bytes=len(payload),
            meta={"backend": "mock", "requested_model": self.MODEL},
        )

    def _answer(self, state: State, question: ChoiceQuestion) -> dict[str, Any]:
        probs = dict(self._probs_fn(state, question))
        if set(probs) != set(question.criteria):
            raise ValueError("probs_fn must return exactly the question's options")
        total = sum(probs.values())
        if total <= 0 or any(p < 0 for p in probs.values()):
            raise ValueError("probs_fn must return non-negative weights with a positive sum")
        probs = {k: v / total for k, v in probs.items()}
        best = max(probs, key=probs.__getitem__)
        # "confidence" is derived by the vendor in an undocumented way; the mock reports the
        # top probability as a placeholder. Nothing in the project may depend on its value.
        return {
            "type": "choice",
            "choice": best,
            "probabilities": probs,
            "confidence": probs[best],
        }

    def close(self) -> None:
        pass

    def __enter__(self) -> MockJevClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
