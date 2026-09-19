"""JevArbiter on the mock client: state building for the three modes, probabilities, timing."""

import json

import numpy as np
import pytest

from flight_or_bite.arbiters.jev_arbiter import MODES, JevArbiter, load_prompt, prompt_hash
from flight_or_bite.arbiters.jev_client import JevResponseError, MockJevClient, build_payload
from flight_or_bite.arena.env import load_env_config
from flight_or_bite.types import Action, Arbiter, Observation

OBS = Observation(sugar=0.637, bitter=0.049, looming=0.2, hunger=0.5)


def test_prompts_load_and_hash():
    for mode in MODES:
        prompt = load_prompt(mode)
        assert prompt.mode == mode and set(prompt.criteria) == {"EAT", "ESCAPE", "IDLE"}
        assert len(prompt_hash(mode)) == 64
    assert len({prompt_hash(m) for m in MODES}) == 3


def test_naive_state_is_only_fields_and_rounded_numbers():
    assert load_prompt("naive").state(OBS) == {
        "sugar": 0.64, "bitter": 0.05, "looming": 0.2, "hunger": 0.5,
    }  # fmt: skip


def test_informed_state_adds_rules_whose_numbers_match_the_environment():
    state = load_prompt("informed").state(OBS)
    assert state["observation"] == load_prompt("naive").state(OBS)
    rules, cfg = state["rules"], load_env_config()
    for number in ("500", "50%", "25%", "20%", "0.3 and 1", "0 and 0.1", "mean 0.7", "mean 0.2",
                   "deviation 0.2", "starts at 50", "exceed 100", "costs 1 energy", "12 times",
                   "15 times", "probability 0.6", "costs 3 energy", "probability 0.3"):  # fmt: skip
        assert number in rules, number
    assert (cfg.max_trials, cfg.p_food, cfg.p_toxic, cfg.p_threat) == (500, 0.5, 0.25, 0.2)
    assert (cfg.eat_gain, cfg.toxic_cost, cfg.escape_cost) == (12.0, 15.0, 3.0)
    assert (cfg.p_death_eat, cfg.p_death_idle) == (0.6, 0.3)
    for hint in ("should", "best", "optimal", "recommend"):
        assert hint not in rules.lower()


@pytest.mark.parametrize(
    ("value", "level"),
    [(0.0, "none"), (0.01, "very low"), (0.199, "very low"), (0.2, "low"), (0.399, "low"),
     (0.4, "medium"), (0.6, "high"), (0.8, "very high"), (1.0, "very high")],
)  # fmt: skip
def test_bucket_boundaries(value, level):
    assert load_prompt("bucketed").level(value) == level


def test_bucketed_state_has_no_numbers():
    state = load_prompt("bucketed").state(OBS)
    assert state == {"sugar": "high", "bitter": "very low", "looming": "low", "hunger": "medium"}


def test_wire_request_of_each_mode_is_valid_json_with_three_options():
    for mode in MODES:
        prompt = load_prompt(mode)
        body = json.loads(build_payload(prompt.state(OBS), {"action": prompt.question()}, "m"))
        assert set(body["questions"]["action"]["criteria"]) == {"EAT", "ESCAPE", "IDLE"}
        assert body["questions"]["action"]["type"] == "choice"


def test_arbiter_samples_from_renormalised_probabilities_and_is_timed():
    def probs_fn(state, question):
        return {"EAT": 3.0, "ESCAPE": 1.0, "IDLE": 0.0}

    client = MockJevClient(latency_s=0.005, probs_fn=probs_fn)
    arbiter = JevArbiter(client, load_prompt("naive"))
    assert isinstance(arbiter, Arbiter) and arbiter.name == "jev_naive"
    rng = np.random.default_rng(0)
    decisions = [arbiter.decide(OBS, rng) for _ in range(200)]
    first = decisions[0]
    assert first.probs == {Action.EAT: 0.75, Action.ESCAPE: 0.25, Action.IDLE: 0.0}
    assert first.t_wall_ns >= 5_000_000 and first.t_wall_ns >= first.meta["t_http_ns"]
    assert first.t_sim_ms is None and first.meta["cache_hit"] is False
    assert first.meta["mode"] == "naive" and first.meta["model_version"] == "mock-jev-0"
    share_eat = np.mean([d.action is Action.EAT for d in decisions])
    assert 0.65 < share_eat < 0.85 and not any(d.action is Action.IDLE for d in decisions)
    assert client.budget.used == 200


def test_unexpected_options_are_rejected():
    class Wrong(MockJevClient):
        def _answer(self, state, question):
            return {"type": "choice", "choice": "EAT", "confidence": 1.0,
                    "probabilities": {"EAT": 1.0, "RUN": 0.0}}  # fmt: skip

    with pytest.raises(JevResponseError):
        JevArbiter(Wrong(), load_prompt("naive")).decide(OBS, np.random.default_rng(0))
