"""MockJevClient: documented response shape, known latency, determinism, call fuse."""

import pytest

from flight_or_bite.arbiters.jev_client import (
    CallBudgetExceeded,
    ChoiceQuestion,
    MockJevClient,
)
from flight_or_bite.timing.timers import Stopwatch
from flight_or_bite.types import Action

QUESTION = ChoiceQuestion(
    instructions="Which action should the agent take?",
    criteria={a.value: None for a in Action},
)
STATE = {"sugar": 0.7, "bitter": 0.05, "looming": 0.6, "hunger": 0.5}

# The mock busy-waits, so overshoot is microseconds; the slack only absorbs preemption.
SLACK_NS = 2_000_000


def test_response_has_documented_shape():
    resp = MockJevClient().evaluate(STATE, {"action": QUESTION})
    assert set(resp.raw) == {"model", "answers", "usage"}
    assert set(resp.raw["answers"]["action"]) == {"type", "choice", "probabilities", "confidence"}
    answer = resp.choice("action")
    assert set(answer.probabilities) == {"EAT", "ESCAPE", "IDLE"}
    assert sum(answer.probabilities.values()) == pytest.approx(1.0)
    assert resp.cache_hit is False
    assert resp.meta["backend"] == "mock"


@pytest.mark.parametrize("delay_s", [0.02, 0.06])
def test_known_latency_is_measured_by_client_and_external_timer(delay_s):
    client = MockJevClient(latency_s=delay_s)
    with Stopwatch() as sw:
        resp = client.evaluate(STATE, {"action": QUESTION})
    delay_ns = int(delay_s * 1e9)
    assert delay_ns <= resp.t_wall_ns <= delay_ns + SLACK_NS
    assert resp.t_wall_ns <= sw.elapsed_ns <= delay_ns + SLACK_NS


def test_random_latency_is_reproducible_by_seed():
    drawn: list[float] = []

    def latency(rng):
        value = float(rng.uniform(0.0, 0.002))
        drawn.append(value)
        return value

    for _ in range(2):
        client = MockJevClient(latency_s=latency, seed=7)
        for _ in range(3):
            client.evaluate(STATE, {"action": QUESTION})
    assert drawn[:3] == drawn[3:]


def test_probs_fn_controls_policy_and_is_normalized():
    def looming_policy(state, question):
        return {"EAT": 1.0 - state["looming"], "ESCAPE": state["looming"], "IDLE": 0.0}

    client = MockJevClient(probs_fn=lambda s, q: {k: 2 * v for k, v in looming_policy(s, q).items()})
    answer = client.evaluate(STATE, {"action": QUESTION}).choice("action")
    assert answer.choice == "ESCAPE"
    assert answer.probabilities == pytest.approx({"EAT": 0.4, "ESCAPE": 0.6, "IDLE": 0.0})


def test_probs_fn_must_cover_exactly_the_options():
    client = MockJevClient(probs_fn=lambda s, q: {"EAT": 1.0})
    with pytest.raises(ValueError):
        client.evaluate(STATE, {"action": QUESTION})


def test_max_calls_fuse():
    client = MockJevClient(max_calls=1)
    client.evaluate(STATE, {"action": QUESTION})
    with pytest.raises(CallBudgetExceeded):
        client.evaluate(STATE, {"action": QUESTION})
