"""JevClient against an in-process transport; the fixture is a captured live response."""

import json

import httpx
import pytest

from flight_or_bite.arbiters.jev_client import (
    CallBudgetExceeded,
    ChoiceQuestion,
    JevAuthError,
    JevClient,
    JevHTTPError,
    JevModelMismatch,
    JevResponseError,
    build_payload,
    is_pinned_model,
)

QUESTION = ChoiceQuestion(
    instructions="Which action should the agent take?",
    criteria={"EAT": "Feed now", "ESCAPE": None, "IDLE": None},
)

# Captured verbatim from the live OpenRouter Decisions endpoint on 2026-09-19.
LIVE_RESPONSE = {
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


def make_client(handler, **kwargs) -> JevClient:
    kwargs.setdefault("log_dir", LOG_DIR[0])
    return JevClient(api_key="test-key", transport=httpx.MockTransport(handler), **kwargs)


LOG_DIR: list = [None]


@pytest.fixture(autouse=True)
def log_dir(tmp_path):
    LOG_DIR[0] = tmp_path / "raw"
    return LOG_DIR[0]


def ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=LIVE_RESPONSE, headers={"x-generation-id": LIVE_RESPONSE["id"]})


def test_request_matches_documented_wire_format():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return ok(request)

    with make_client(handler) as client:
        client.evaluate({"sugar": 0.7}, {"action": QUESTION})

    request = seen["request"]
    assert request.method == "POST"
    assert str(request.url) == "https://openrouter.ai/api/alpha/decisions"
    assert request.headers["authorization"] == "Bearer test-key"
    assert request.headers["content-type"] == "application/json"
    assert request.headers["x-openrouter-cache"] == "false"  # timed calls are never cached
    assert json.loads(request.content) == {
        "state": {"sugar": 0.7},
        "model": "typesafe/jev-1.13",
        "questions": {
            "action": {
                "type": "choice",
                "instructions": "Which action should the agent take?",
                "criteria": {"EAT": "Feed now", "ESCAPE": None, "IDLE": None},
            }
        },
    }


def test_parses_live_response_and_measures_only_client_wall_time():
    with make_client(ok) as client:
        resp = client.evaluate({"sugar": 0.7}, {"action": QUESTION})

    answer = resp.choice("action")
    assert answer.choice == "ESCAPE"
    assert answer.probabilities == {"EAT": 0.4, "IDLE": 0.02, "ESCAPE": 0.58}
    assert answer.confidence == 0.37
    assert resp.model == "typesafe/jev-1.13-20260917"
    assert resp.meta["requested_model"] == "typesafe/jev-1.13"
    assert resp.meta["provider"] == "TypeSafe"
    assert resp.meta["cost_usd"] == pytest.approx(1.4028e-05)
    assert resp.request_id == LIVE_RESPONSE["id"]
    assert resp.raw == LIVE_RESPONSE
    assert resp.cache_hit is False
    assert resp.request_bytes == len(
        build_payload({"sugar": 0.7}, {"action": QUESTION}, client.model)
    )
    assert resp.t_wall_ns > 0
    assert not hasattr(resp, "timings")  # no connection breakdown, no server time (D10)


@pytest.mark.parametrize(
    ("reported", "accepted"),
    [
        ("typesafe/jev-1.13", True),
        ("typesafe/jev-1.13-20260917", True),
        ("typesafe/jev-1.14-20261101", False),
        ("typesafe/jev-1.130", False),
        ("typesafe/jev-latest", False),
    ],
)
def test_model_pin(reported, accepted):
    assert is_pinned_model(reported) is accepted
    body = {**LIVE_RESPONSE, "model": reported}
    with make_client(lambda request: httpx.Response(200, json=body)) as client:
        if accepted:
            assert client.evaluate("s", {"action": QUESTION}).model == reported
        else:
            with pytest.raises(JevModelMismatch):
                client.evaluate("s", {"action": QUESTION})


def test_payload_bytes_are_stable_under_key_order():
    a = build_payload({"sugar": 0.5, "bitter": 0.1}, {"q": QUESTION}, "m")
    b = build_payload({"bitter": 0.1, "sugar": 0.5}, {"q": QUESTION}, "m")
    assert a == b


@pytest.mark.parametrize("status", [401, 402, 429, 502, 529])
def test_documented_error_statuses_raise_without_retry(status):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            status, json={"error": {"code": status}}, headers={"x-generation-id": "g"}
        )

    with make_client(handler) as client:
        with pytest.raises(JevHTTPError) as excinfo:
            client.evaluate("s", {"q": QUESTION})

    assert excinfo.value.status == status
    assert excinfo.value.request_id == "g"
    assert len(calls) == 1  # retries would corrupt latency measurements


@pytest.mark.parametrize(
    "body",
    [
        {"answers": {}, "usage": {}},  # no model
        {"model": "typesafe/jev-1.13", "answers": [], "usage": {}},  # wrong type
        ["not", "an", "object"],
    ],
)
def test_malformed_body_is_rejected(body):
    with make_client(lambda request: httpx.Response(200, json=body)) as client:
        with pytest.raises(JevResponseError):
            client.evaluate("s", {"q": QUESTION})


def test_choice_accessor_rejects_wrong_type_and_missing_question():
    body = {**LIVE_RESPONSE, "answers": {"q": {"type": "noul", "noul": 0.9}}}
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
        return ok(request)

    with make_client(handler, max_calls=2) as client:
        client.evaluate("s", {"action": QUESTION})
        client.evaluate("s", {"action": QUESTION})
        with pytest.raises(CallBudgetExceeded):
            client.evaluate("s", {"action": QUESTION})

    assert len(calls) == 2
    assert client.budget.used == 2


def test_failed_calls_still_spend_budget():
    with make_client(lambda request: httpx.Response(529), max_calls=5) as client:
        with pytest.raises(JevHTTPError):
            client.evaluate("s", {"q": QUESTION})
    assert client.budget.used == 1


def test_api_key_comes_from_openrouter_variable_only(monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "ignored")  # the direct TypeSafe path is gone (D10)
    with pytest.raises(JevAuthError, match="OPENROUTER_API_KEY"):
        JevClient()
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        return ok(request)

    with JevClient(transport=httpx.MockTransport(handler)) as client:
        client.evaluate("s", {"action": QUESTION})
    assert seen["auth"] == "Bearer from-env"


def test_empty_questions_rejected():
    with pytest.raises(ValueError):
        build_payload("s", {}, "m")


def read_log(directory):
    files = sorted(directory.glob("*.jsonl"))
    assert len(files) == 1
    return [json.loads(line) for line in files[0].read_text().splitlines()]


def test_every_call_is_logged_raw_without_credentials(log_dir):
    with make_client(ok) as client:
        client.evaluate({"sugar": 0.7}, {"action": QUESTION})
        client.evaluate({"sugar": 0.1}, {"action": QUESTION})

    records = read_log(log_dir)
    assert [r["call"] for r in records] == [1, 2]
    first = records[0]
    assert first["status"] == 200 and first["generation_id"] == LIVE_RESPONSE["id"]
    assert first["request"]["state"] == {"sugar": 0.7}
    assert first["request"]["model"] == "typesafe/jev-1.13"
    assert json.loads(first["response_text"]) == LIVE_RESPONSE  # raw text, not a re-serialisation
    assert first["t_wall_ns"] > 0 and first["cache_hit"] is False
    assert "test-key" not in (log_dir / next(iter(p.name for p in log_dir.iterdir()))).read_text()


def test_failures_are_logged_before_they_raise(log_dir):
    bad_model = {**LIVE_RESPONSE, "model": "typesafe/jev-1.14"}
    responses = iter(
        [httpx.Response(429, text="slow down"), httpx.Response(200, text="not json"),
         httpx.Response(200, json=bad_model)]
    )  # fmt: skip
    with make_client(lambda request: next(responses)) as client:
        for expected in (JevHTTPError, JevResponseError, JevModelMismatch):
            with pytest.raises(expected):
                client.evaluate("s", {"action": QUESTION})

    records = read_log(log_dir)
    assert [r["status"] for r in records] == [429, 200, 200]
    assert records[0]["response_text"] == "slow down"
    assert records[1]["response_text"] == "not json"
    assert json.loads(records[2]["response_text"])["model"] == "typesafe/jev-1.14"


def test_call_ledger_persists_across_clients_and_enforces_the_budget(tmp_path):
    ledger = tmp_path / "ledger.json"
    with make_client(ok, ledger=ledger, max_calls=3) as first:
        first.evaluate("s", {"action": QUESTION})
        first.evaluate("s", {"action": QUESTION})
    assert json.loads(ledger.read_text())["calls"] == 2

    with make_client(ok, ledger=ledger, max_calls=3) as second:  # a later run
        assert second.budget.used == 2 and second.budget.session == 0
        second.evaluate("s", {"action": QUESTION})
        with pytest.raises(CallBudgetExceeded):
            second.evaluate("s", {"action": QUESTION})
    assert json.loads(ledger.read_text())["calls"] == 3

    with make_client(ok, ledger=None, max_calls=1) as isolated:  # in-process only
        isolated.evaluate("s", {"action": QUESTION})
    assert json.loads(ledger.read_text())["calls"] == 3
