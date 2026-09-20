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
    assert len({prompt_hash(m) for m in MODES}) == 4 == len(MODES)


def test_naive_state_is_only_fields_and_rounded_numbers():
    assert load_prompt("naive").state(OBS) == {
        "sugar": 0.64, "bitter": 0.05, "looming": 0.2, "hunger": 0.5,
    }  # fmt: skip


def test_informed_puts_the_rules_into_instructions_and_keeps_the_state_bare():
    prompt = load_prompt("informed")
    assert prompt.state(OBS) == load_prompt("naive").state(OBS)  # observation only (D46)
    text, cfg = prompt.question().instructions, load_env_config()
    assert text.endswith("\n\nWhich action should the agent take on this trial?")
    expected = [
        "500", "30%", "25%", "20%", "0.3 and 1", "0 and 0.1", "mean 0.7", "mean 0.2",
        "deviation 0.2", "starts at 50", "exceed 100", "Every trial costs 1 energy", "8 times",
        "15 times", "probability 0.6", "ESCAPE costs an additional 1 energy", "probability 0.3",
        "hunger = 1 − (energy / 100): 0 means full energy, 1 means about to starve.",
        "IDLE has no additional cost.",
    ]  # fmt: skip
    for number in expected:
        assert number in text, number
    assert (cfg.max_trials, cfg.p_food, cfg.p_toxic, cfg.p_threat) == (500, 0.3, 0.25, 0.2)
    assert (cfg.eat_gain, cfg.toxic_cost, cfg.escape_cost) == (8.0, 15.0, 1.0)
    assert (cfg.p_death_eat, cfg.p_death_idle) == (0.6, 0.3)
    for hint in ("should eat", "should escape", "best", "optimal", "recommend"):
        assert hint not in text.lower()


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


def test_arbiter_acts_with_jevs_own_choice_and_can_sample_for_the_secondary_analysis():
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
    assert all(d.action is Action.EAT for d in decisions)  # D27: the response's `choice` field
    assert client.budget.used == 200

    sampler = JevArbiter(MockJevClient(probs_fn=probs_fn), load_prompt("naive"))
    sampler.sample_from_probs = True  # secondary analysis (SPEC §7)
    sampled = [sampler.decide(OBS, rng) for _ in range(300)]
    share_eat = np.mean([d.action is Action.EAT for d in sampled])
    assert 0.65 < share_eat < 0.85 and not any(d.action is Action.IDLE for d in sampled)


def test_unexpected_options_are_rejected():
    class Wrong(MockJevClient):
        def _answer(self, state, question):
            return {"type": "choice", "choice": "EAT", "confidence": 1.0,
                    "probabilities": {"EAT": 1.0, "RUN": 0.0}}  # fmt: skip

    with pytest.raises(JevResponseError):
        JevArbiter(Wrong(), load_prompt("naive")).decide(OBS, np.random.default_rng(0))


def test_two_by_two_design_of_state_modes():
    """rules package: no / yes  x  observation: numbers / named levels."""
    prompts = {m: load_prompt(m) for m in MODES}
    numbers = {"sugar": 0.64, "bitter": 0.05, "looming": 0.2, "hunger": 0.5}
    levels = {"sugar": "high", "bitter": "very low", "looming": "low", "hunger": "medium"}
    assert prompts["naive"].state(OBS) == prompts["informed"].state(OBS) == numbers
    assert prompts["bucketed"].state(OBS) == prompts["informed_bucketed"].state(OBS) == levels
    question = "Which action should the agent take on this trial?"
    assert all(p.version == "v1" and p.instructions == question for p in prompts.values())
    # the "rules" factor is a package: rules text AND option descriptions, together or not at all
    for mode, p in prompts.items():
        described = all(v is not None for v in p.criteria.values())
        assert bool(p.rules) == ("informed" in mode) == described
        assert (p.full_instructions == question) == ("informed" not in mode)
    a, b = prompts["informed"].rules, prompts["informed_bucketed"].rules
    assert "four numbers between 0 and 1" in a and "reported as a level" in b
    tail = "`sugar` is the amount of food present"
    assert a[a.index(tail) :] == b[b.index(tail) :]
    assert prompts["informed"].criteria == prompts["informed_bucketed"].criteria


def test_bucketed_state_key_collapses_observations_into_identical_requests():
    p = load_prompt("bucketed")
    near = Observation(sugar=0.61, bitter=0.01, looming=0.39, hunger=0.59)
    far = Observation(sugar=0.61, bitter=0.01, looming=0.41, hunger=0.59)
    assert p.state_key(OBS) == p.state_key(near) != p.state_key(far)


def test_retries_are_off_by_default_and_flagged_when_used(monkeypatch):
    import httpx

    from flight_or_bite.arbiters import jev_arbiter

    monkeypatch.setattr(jev_arbiter.time, "sleep", lambda s: None)

    class Flaky(MockJevClient):
        failures = 2

        def evaluate(self, state, questions):
            if Flaky.failures:
                Flaky.failures -= 1
                raise httpx.ConnectError("boom")
            return super().evaluate(state, questions)

    with pytest.raises(httpx.ConnectError):
        JevArbiter(Flaky(), load_prompt("naive")).decide(OBS, np.random.default_rng(0))
    Flaky.failures = 2
    arbiter = JevArbiter(Flaky(), load_prompt("naive"), retries=3)
    assert arbiter.decide(OBS, np.random.default_rng(0)).meta["retried"] == 2


def test_native_action_of_the_baselines_is_their_argmax():
    from flight_or_bite.arbiters.baselines import FixedPriorityArbiter, RandomArbiter

    rng = np.random.default_rng(0)
    assert FixedPriorityArbiter().decide(Observation(0.5, 0.0, 0.9, 0.5), rng).action is Action.ESCAPE
    picks = {RandomArbiter().decide(OBS, rng).action for _ in range(60)}
    assert picks == set(Action)  # exact ties are broken at random
