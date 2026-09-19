"""JevClient against an in-process transport; fixtures mirror the documented API examples."""

import json

import httpx
import pytest

from flight_or_bite.arbiters.jev_client import (
    OPENROUTER,
    TYPESAFE,
    CallBudgetExceeded,
    ChoiceQuestion,
    JevAuthError,
    JevClient,
    JevHTTPError,
    JevResponseError,
    build_payload,
    resolve_backend,
)

QUESTION = ChoiceQuestion(
    instructions="Which team should handle this?",
    criteria={
        "billing": "Payments, invoicing, refunds",
        "technical": "Bugs, outages, integrations",
        "sales": None,
    },
)

# Shape from https://docs.typesafe.ai/api.md ("Choice answer"), versioned model id per /models.md
DOCUMENTED_RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "department": {
            "type": "choice",
            "choice": "technical",
            "probabilities": {"billing": 0.08, "technical": 0.85, "sales": 0.07},
            "confidence": 0.82,
        }
    },
    "usage": {"input_tokens": 312, "output_tokens": 48},
}


def make_client(handler, **kwargs) -> JevClient:
    return JevClient(api_key="test-key", transport=httpx.MockTransport(handler), **kwargs)


def test_request_matches_documented_wire_format():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(200, json=DOCUMENTED_RESPONSE)

    with make_client(handler) as client:
        client.evaluate("Help! My payouts have been failing.", {"department": QUESTION})

    request = seen["request"]
    assert request.method == "POST"
    assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
    assert request.headers["authorization"] == "Bearer test-key"
    assert request.headers["content-type"] == "application/json"
    assert json.loads(request.content) == {
        "state": "Help! My payouts have been failing.",
        "model": "jev-latest",
        "questions": {
            "department": {
                "type": "choice",
                "instructions": "Which team should handle this?",
                "criteria": {
                    "billing": "Payments, invoicing, refunds",
                    "technical": "Bugs, outages, integrations",
                    "sales": None,
                },
            }
        },
    }


def test_parses_documented_response_and_metadata():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=DOCUMENTED_RESPONSE, headers={"x-typesafe-request-id": "req_123"}
        )

    with make_client(handler) as client:
        resp = client.evaluate({"sugar": 0.5}, {"department": QUESTION})

    answer = resp.choice("department")
    assert answer.choice == "technical"
    assert answer.probabilities == {"billing": 0.08, "technical": 0.85, "sales": 0.07}
    assert answer.confidence == 0.82
    assert resp.model == "jev-1.13.0"
    assert resp.meta["requested_model"] == "jev-latest"
    assert resp.usage == {"input_tokens": 312, "output_tokens": 48}
    assert resp.request_id == "req_123"
    assert resp.raw == DOCUMENTED_RESPONSE
    assert resp.cache_hit is False
    assert resp.request_bytes == len(
        build_payload({"sugar": 0.5}, {"department": QUESTION}, "jev-latest")
    )
    assert resp.timings.total_ns > 0


def test_payload_bytes_are_stable_under_key_order():
    a = build_payload({"sugar": 0.5, "bitter": 0.1}, {"q": QUESTION}, "jev-latest")
    b = build_payload({"bitter": 0.1, "sugar": 0.5}, {"q": QUESTION}, "jev-latest")
    assert a == b


@pytest.mark.parametrize("status", [401, 422, 429, 529])
def test_documented_error_statuses_raise_without_retry(status):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            status, json={"error": "nope"}, headers={"x-typesafe-request-id": "r"}
        )

    with make_client(handler) as client:
        with pytest.raises(JevHTTPError) as excinfo:
            client.evaluate("s", {"q": QUESTION})

    assert excinfo.value.status == status
    assert excinfo.value.request_id == "r"
    assert len(calls) == 1  # retries would corrupt latency measurements


@pytest.mark.parametrize(
    "body",
    [
        {"answers": {}, "usage": {}},  # no model
        {"model": "jev-1.13.0", "answers": [], "usage": {}},  # wrong type
        ["not", "an", "object"],
    ],
)
def test_malformed_body_is_rejected(body):
    with make_client(lambda request: httpx.Response(200, json=body)) as client:
        with pytest.raises(JevResponseError):
            client.evaluate("s", {"q": QUESTION})


def test_choice_accessor_rejects_wrong_type_and_missing_question():
    body = {
        "model": "jev-1.13.0",
        "answers": {"q": {"type": "noul", "noul": 0.9}},
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    with make_client(lambda request: httpx.Response(200, json=body)) as client:
        resp = client.evaluate("s", {"q": QUESTION})
    with pytest.raises(JevResponseError):
        resp.choice("q")
    with pytest.raises(JevResponseError):
        resp.choice("absent")


def test_max_calls_fuse_stops_before_the_network():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=DOCUMENTED_RESPONSE)

    with make_client(handler, max_calls=2) as client:
        client.evaluate("s", {"department": QUESTION})
        client.evaluate("s", {"department": QUESTION})
        with pytest.raises(CallBudgetExceeded):
            client.evaluate("s", {"department": QUESTION})

    assert len(calls) == 2
    assert client.budget.used == 2


def test_failed_calls_still_spend_budget():
    with make_client(lambda request: httpx.Response(529), max_calls=5) as client:
        with pytest.raises(JevHTTPError):
            client.evaluate("s", {"q": QUESTION})
    assert client.budget.used == 1


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(JevAuthError):
        JevClient()


def test_api_key_from_environment_prefers_spec_name(monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "from-jev")
    monkeypatch.setenv("TYPESAFE_API_KEY", "from-typesafe")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json=DOCUMENTED_RESPONSE)

    with JevClient(transport=httpx.MockTransport(handler)) as client:
        client.evaluate("s", {"department": QUESTION})
    assert seen["auth"] == "Bearer from-jev"


def test_empty_questions_rejected():
    with pytest.raises(ValueError):
        build_payload("s", {}, "jev-latest")


# Captured verbatim from the live OpenRouter Decisions endpoint on 2026-09-19.
OPENROUTER_LIVE_RESPONSE = {
    "model": "typesafe/jev-1.13-20260917",
    "answers": {
        "action": {
            "type": "choice",
            "choice": "ESCAPE",
            "probabilities": {"EAT": 0.4, "IDLE": 0.02, "ESCAPE": 0.58},
            "confidence": 0.37,
        }
    },
    "usage": {"input_tokens": 334, "output_tokens": 42, "cost": 1.4028e-05},
    "id": "gen-dec-1789836928-raVd9dvG1y1ZfmsFcnZ3",
    "provider": "TypeSafe",
}
ACTION_QUESTION = ChoiceQuestion(
    instructions="Which action should the agent take?",
    criteria={"EAT": None, "ESCAPE": None, "IDLE": None},
)


def test_openrouter_backend_wire_format_and_parsing():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(
            200,
            json=OPENROUTER_LIVE_RESPONSE,
            headers={"x-generation-id": OPENROUTER_LIVE_RESPONSE["id"]},
        )

    client = JevClient(api_key="or-key", backend=OPENROUTER, transport=httpx.MockTransport(handler))
    with client:
        resp = client.evaluate({"sugar": 0.7}, {"action": ACTION_QUESTION})

    request = seen["request"]
    assert str(request.url) == "https://openrouter.ai/api/alpha/decisions"
    assert request.headers["authorization"] == "Bearer or-key"
    assert request.headers["x-openrouter-cache"] == "false"
    body = json.loads(request.content)
    assert body["model"] == "typesafe/jev-1.13"
    assert set(body) == {"state", "model", "questions"}

    assert resp.choice("action").probabilities == {"EAT": 0.4, "IDLE": 0.02, "ESCAPE": 0.58}
    assert resp.model == "typesafe/jev-1.13-20260917"
    assert resp.request_id == "gen-dec-1789836928-raVd9dvG1y1ZfmsFcnZ3"
    assert resp.meta["backend"] == "openrouter-decisions"
    assert resp.meta["provider"] == "TypeSafe"
    assert resp.meta["cost_usd"] == pytest.approx(1.4028e-05)


def test_resolve_backend(monkeypatch):
    with pytest.raises(JevAuthError):
        resolve_backend("auto")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    assert resolve_backend("auto") is OPENROUTER
    monkeypatch.setenv("JEV_API_KEY", "k")
    assert resolve_backend("auto") is TYPESAFE  # the direct path wins when both keys exist
    assert resolve_backend("openrouter") is OPENROUTER
    with pytest.raises(ValueError):
        resolve_backend("bogus")


def test_openrouter_key_is_not_used_for_the_typesafe_backend(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    with pytest.raises(JevAuthError):
        JevClient(backend=TYPESAFE)
