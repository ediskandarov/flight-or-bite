"""Jev clients: real HTTP client and a mock with configurable latency (SPEC §4.3).

Everything about the wire format comes from docs/jev_api_notes.md (official TypeSafe and
OpenRouter docs). Both backends accept the same body: {"state", "model", "questions"}.
The official SDK is deliberately not used: its default retry policy would hide several
network round trips inside one "call" and contaminate latency measurements.
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

DEFAULT_TIMEOUT_S = 10.0  # the vendor SDK's documented default
DEFAULT_MAX_CALLS = 100_000  # SPEC §4.3 says 30 000; raised by decision D8 (docs/decisions.md)


@dataclass(frozen=True)
class JevBackend:
    """One documented way of reaching Jev."""

    name: str
    base_url: str
    path: str
    default_model: str
    api_key_env: tuple[str, ...]
    request_id_header: str
    extra_headers: Mapping[str, str] = field(default_factory=dict)


# https://docs.typesafe.ai/api.md
# SPEC §4.3 names JEV_API_KEY; the vendor's own tooling uses TYPESAFE_API_KEY.
TYPESAFE = JevBackend(
    name="typesafe-http",
    base_url="https://api.typesafe.ai",
    path="/v1/systemone",
    default_model="jev-latest",
    api_key_env=("JEV_API_KEY", "TYPESAFE_API_KEY"),
    request_id_header="x-typesafe-request-id",
)

# https://openrouter.ai/docs/api/api-reference/alphadecisions/ (alpha). OpenRouter's response
# cache is opt-in and does not list this endpoint; the header states our intent regardless.
OPENROUTER = JevBackend(
    name="openrouter-decisions",
    base_url="https://openrouter.ai",
    path="/api/alpha/decisions",
    default_model="typesafe/jev-1.13",
    api_key_env=("OPENROUTER_API_KEY",),
    request_id_header="x-generation-id",
    extra_headers={"X-OpenRouter-Cache": "false"},
)

BACKENDS = {"typesafe": TYPESAFE, "openrouter": OPENROUTER}


def _key_from_env(backend: JevBackend) -> str | None:
    return next((os.environ[v] for v in backend.api_key_env if os.environ.get(v)), None)


def resolve_backend(name: str = "auto") -> JevBackend:
    """'auto' picks the first backend with a key, preferring the direct path (fewer hops)."""
    if name != "auto":
        try:
            return BACKENDS[name]
        except KeyError as e:
            raise ValueError(
                f"unknown backend {name!r}; expected auto, {', '.join(BACKENDS)}"
            ) from e
    for backend in BACKENDS.values():
        if _key_from_env(backend):
            return backend
    every = [v for b in BACKENDS.values() for v in b.api_key_env]
    raise JevAuthError(f"no API key: set one of {', '.join(every)}")


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
class JevTimings:
    total_ns: int
    connect_ns: int | None = None  # None when the keep-alive connection was reused
    ttfb_ns: int | None = None  # request start -> response headers received


@dataclass(frozen=True)
class JevResponse:
    model: str  # as reported by the server
    answers: dict[str, Any]
    usage: dict[str, Any]
    raw: dict[str, Any]
    timings: JevTimings
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


class _Trace:
    """Collects httpcore trace events to split latency into connect / first byte / total."""

    def __init__(self) -> None:
        self.events: dict[str, int] = {}

    def __call__(self, name: str, info: Mapping[str, Any]) -> None:
        self.events.setdefault(name, time.perf_counter_ns())

    def _first(self, suffix: str) -> int | None:
        return next((t for n, t in self.events.items() if n.endswith(suffix)), None)

    def connect_ns(self) -> int | None:
        start = self._first("connect_tcp.started")
        end = self._first("start_tls.complete") or self._first("connect_tcp.complete")
        return end - start if start is not None and end is not None else None

    def ttfb_ns(self, t0: int) -> int | None:
        headers = self._first("receive_response_headers.complete")
        return headers - t0 if headers is not None else None


class JevClient:
    """Real Jev client over one keep-alive session. No retries, no cache."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        backend: JevBackend = TYPESAFE,
        model: str | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_calls: int = DEFAULT_MAX_CALLS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        api_key = api_key or _key_from_env(backend)
        if not api_key:
            raise JevAuthError(f"no API key: set one of {', '.join(backend.api_key_env)}")
        self.backend = backend
        self.model = model or backend.default_model
        self.budget = CallBudget(max_calls)
        self._http = httpx.Client(
            base_url=backend.base_url,
            timeout=timeout_s,
            transport=transport,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                **backend.extra_headers,
            },
        )

    def evaluate(self, state: State, questions: Mapping[str, ChoiceQuestion]) -> JevResponse:
        payload = build_payload(state, questions, self.model)
        self.budget.spend()
        trace = _Trace()
        t0 = time.perf_counter_ns()
        resp = self._http.post(self.backend.path, content=payload, extensions={"trace": trace})
        total_ns = time.perf_counter_ns() - t0

        request_id = resp.headers.get(self.backend.request_id_header)
        if resp.status_code != 200:
            raise JevHTTPError(resp.status_code, resp.text, request_id)
        try:
            raw = resp.json()
        except ValueError as e:
            raise JevResponseError(f"response is not JSON: {resp.text[:500]}") from e
        model, answers, usage = _parse_body(raw)
        return JevResponse(
            model=model,
            answers=answers,
            usage=usage,
            raw=raw,
            timings=JevTimings(
                total_ns=total_ns, connect_ns=trace.connect_ns(), ttfb_ns=trace.ttfb_ns(t0)
            ),
            request_bytes=len(payload),
            request_id=request_id,
            meta={
                "backend": self.backend.name,
                "requested_model": self.model,
                "http_version": resp.http_version,
                # OpenRouter only: upstream provider and billed cost in USD
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
        total_ns = time.perf_counter_ns() - t0
        return JevResponse(
            model=self.MODEL,
            answers=answers,
            usage=raw["usage"],
            raw=raw,
            timings=JevTimings(total_ns=total_ns),
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
