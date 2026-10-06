"""No real API: direct routing, shared budget, resume isolation and spend accounting."""

import json
import runpy
from pathlib import Path

import httpx
import pytest
from rich.console import Console

from flight_or_bite.arbiters.jev_client import ChoiceQuestion, JevAuthError, JevModelMismatch, MockJevClient
from flight_or_bite.arbiters.typesafe_client import MODEL, TypeSafeClient
from flight_or_bite.timing.typesafe_spend import update_spend

QUESTION = ChoiceQuestion("Choose", {"EAT": None, "ESCAPE": None, "IDLE": None})
BODY = {"model": MODEL, "answers": {"action": {"type": "choice", "choice": "EAT",
        "probabilities": {"EAT": 0.8, "ESCAPE": 0.1, "IDLE": 0.1}, "confidence": 0.8}},
        "usage": {"input_tokens": 741, "output_tokens": 0}}


def test_direct_routing_response_and_budget(tmp_path):
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(200, json=BODY)

    with TypeSafeClient("test-secret", log_dir=tmp_path / "raw", ledger=tmp_path / "ledger.json",
                        transport=httpx.MockTransport(respond)) as client:
        result = client.evaluate({"sugar": 0.5}, {"action": QUESTION})
    assert str(seen[0].url) == "https://api.typesafe.ai/v1/systemone"
    assert seen[0].headers["authorization"] == "Bearer test-secret"
    assert json.loads(seen[0].content)["model"] == MODEL
    assert result.choice("action").choice == "EAT"
    assert json.loads((tmp_path / "ledger.json").read_text())["calls"] == 1
    assert "test-secret" not in next((tmp_path / "raw").glob("*.jsonl")).read_text()


@pytest.mark.parametrize(("status", "body", "error"), [
    (401, {"message": "test-secret"}, JevAuthError),
    (402, {}, JevAuthError),
    (200, {**BODY, "model": "jev-1.14.0"}, JevModelMismatch),
])
def test_auth_or_model_error_stops_and_is_logged(tmp_path, status, body, error):
    with TypeSafeClient("test-secret", log_dir=tmp_path / "raw", ledger=tmp_path / "ledger.json",
                        transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body))) as client:
        with pytest.raises(error):
            client.evaluate({}, {"action": QUESTION})
    text = next((tmp_path / "raw").glob("*.jsonl")).read_text()
    assert "test-secret" not in text
    assert json.loads(text)["status"] == status


def test_transport_failure_is_accounted_as_unknown_usage(tmp_path):
    def fail(request):
        raise httpx.ReadTimeout("timeout")

    with TypeSafeClient("test-secret", log_dir=tmp_path / "bench/raw/informed",
                        ledger=tmp_path / "ledger.json", transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(httpx.ReadTimeout):
            client.evaluate({}, {"action": QUESTION})
    (tmp_path / "opening_balance.json").write_text('{"balance_usd":"5.00"}')
    summary = update_spend(tmp_path, tmp_path / "bench")
    assert summary["tracked_attempts"] == 1
    assert summary["calls_with_unknown_usage"] == 1
    assert summary["estimated_balance_usd"] is None


def test_spend_combines_probe_and_bench_without_double_counting(tmp_path):
    (tmp_path / "opening_balance.json").write_text('{"balance_usd":"5.00"}')
    (tmp_path / "probe").mkdir()
    (tmp_path / "probe/summary.json").write_text(json.dumps({"attempts": 1, "known_input_tokens": 741,
        "estimated_known_cost_usd": "0.000031122", "calls_with_unknown_usage": 0}))
    raw = tmp_path / "bench/raw/informed"
    raw.mkdir(parents=True)
    (raw / "calls.jsonl").write_text(json.dumps({"response_text": json.dumps(BODY)}) + "\n")
    first = update_spend(tmp_path, tmp_path / "bench")
    assert first == update_spend(tmp_path, tmp_path / "bench")
    assert first["tracked_attempts"] == 2
    assert first["known_input_tokens"] == 1482
    assert first["estimated_known_spend_usd"] == "0.000062244"


def test_full_runner_preserves_original_and_resumes(tmp_path, monkeypatch):
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/jev_direct_bench.py"))
    run = module["run"]
    state = run.__globals__
    monkeypatch.setattr(state["prereg"], "check", lambda: None)
    monkeypatch.setattr(state["bench"], "load_cfg", lambda: {"n": 3, "warmup": 2, "state_seed": 7,
                        "jev_modes": ["naive", "informed"], "max_error_share": 0.05, "deadlines_ms": [100]})
    monkeypatch.setitem(state, "throttle_check", lambda: {"timer_throttled": False, "power": "AC Power"})
    monkeypatch.setitem(state, "start_run", lambda *a, **kw: tmp_path / "run")
    monkeypatch.setitem(state, "update_spend", lambda **kw: None)
    original = tmp_path / "original"
    original.mkdir()
    (original / "untouched.txt").write_bytes(b"keep existing results")
    out = tmp_path / "direct"
    factory = lambda **kw: MockJevClient()  # noqa: E731
    run(Console(quiet=True), out, original, factory)
    before = {p.name: p.read_bytes() for p in out.glob("*.jsonl")}
    run(Console(quiet=True), out, original, factory)
    assert before == {p.name: p.read_bytes() for p in out.glob("*.jsonl")}
    assert (original / "untouched.txt").read_bytes() == b"keep existing results"
    for text in before.values():
        rows = [json.loads(line) for line in text.splitlines()]
        assert len(rows) == 5 and sum(not r["warmup"] for r in rows) == 3
    with pytest.raises(ValueError, match="preserved OpenRouter"):
        run(Console(quiet=True), original, original, factory)
    protocol = json.loads((out / "protocol.json").read_text())
    protocol["model"] = "other"
    (out / "protocol.json").write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="protocol differs"):
        run(Console(quiet=True), out, original, factory)


def test_runner_refuses_bad_power_before_writing_or_calling(tmp_path, monkeypatch):
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/jev_direct_bench.py"))
    run = module["run"]
    monkeypatch.setitem(run.__globals__, "throttle_check", lambda: {"timer_throttled": False, "power": "Battery"})
    with pytest.raises(RuntimeError, match="AC power"):
        run(Console(quiet=True), tmp_path / "direct", tmp_path / "original")
    assert not (tmp_path / "direct").exists()
