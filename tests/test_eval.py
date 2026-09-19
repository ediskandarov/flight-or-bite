"""Statistics, baselines and the episode runner."""

import numpy as np
import pytest

from flight_or_bite.arbiters.base import sample_action
from flight_or_bite.arbiters.baselines import FixedPriorityArbiter, RandomArbiter
from flight_or_bite.arena.env import Arena, load_env_config
from flight_or_bite.eval.episodes import run_episode
from flight_or_bite.eval.stats import bootstrap_mean_ci, paired_bootstrap, percent_of_oracle
from flight_or_bite.types import Action, Arbiter, Decision, Observation

CFG = load_env_config()


def test_paired_bootstrap_detects_a_shift_and_not_noise():
    rng = np.random.default_rng(0)
    base = rng.normal(100, 30, 400)
    shifted = paired_bootstrap(base + 5 + rng.normal(0, 3, 400), base, rng, n=3000)
    assert shifted.significant and shifted.ci_low < 5 < shifted.ci_high
    assert shifted.mean_diff == pytest.approx(5, abs=0.5)
    jitter = rng.normal(0, 3, 200)
    noise = paired_bootstrap(base + np.concatenate([jitter, -jitter]), base, rng, n=3000)  # mean 0
    assert not noise.significant and noise.ci_low < 0 < noise.ci_high
    with pytest.raises(ValueError):
        paired_bootstrap(base, base[:-1], rng)


def test_pairing_is_tighter_than_an_unpaired_interval():
    rng = np.random.default_rng(1)
    base = rng.normal(100, 50, 300)
    paired = paired_bootstrap(base + 2, base, rng, n=2000)
    lo, hi = bootstrap_mean_ci(base, rng, n=2000)
    assert (paired.ci_high - paired.ci_low) < 0.01 < (hi - lo)


def test_percent_of_oracle():
    assert percent_of_oracle(15, 15, 150) == 0 and percent_of_oracle(150, 15, 150) == 1
    assert percent_of_oracle(82.5, 15, 150) == pytest.approx(0.5)


def test_fixed_priority_rules():
    fixed = FixedPriorityArbiter()
    pick = lambda **kw: max(fixed.policy(Observation(**kw))[0].items(), key=lambda x: x[1])[0]  # noqa: E731
    assert pick(sugar=0.9, bitter=0.0, looming=0.51, hunger=0.5) is Action.ESCAPE
    assert pick(sugar=0.9, bitter=0.0, looming=0.5, hunger=0.5) is Action.EAT  # strictly greater
    assert pick(sugar=0.9, bitter=0.3, looming=0.1, hunger=0.5) is Action.IDLE  # bitter not < 0.3
    assert pick(sugar=0.0, bitter=0.0, looming=0.1, hunger=0.5) is Action.IDLE


def test_random_arbiter_is_uniform_and_every_arbiter_is_timed():
    arbiter = RandomArbiter()
    assert isinstance(arbiter, Arbiter)
    rng = np.random.default_rng(0)
    obs = Observation(0.5, 0.0, 0.2, 0.5)
    decisions = [arbiter.decide(obs, rng) for _ in range(3000)]
    share = {a: sum(d.action is a for d in decisions) / 3000 for a in Action}
    assert all(abs(s - 1 / 3) < 0.04 for s in share.values())
    assert all(isinstance(d, Decision) and d.t_wall_ns > 0 for d in decisions[:10])


def test_sample_action_validates_probabilities():
    rng = np.random.default_rng(0)
    assert sample_action({Action.EAT: 2.0}, rng) is Action.EAT  # unnormalised is fine
    with pytest.raises(ValueError):
        sample_action({Action.EAT: -1.0, Action.IDLE: 2.0}, rng)
    with pytest.raises(ValueError):
        sample_action({}, rng)


def test_episode_runner_is_reproducible_and_counts_actions():
    a = run_episode(Arena(CFG), RandomArbiter(), 5)
    b = run_episode(Arena(CFG), RandomArbiter(), 5)
    assert a == b or a.as_dict() | {"t_wall_ns_median": 0} == b.as_dict() | {"t_wall_ns_median": 0}
    # every trial the agent entered was decided, including the one it died on
    assert a.n_eat + a.n_escape + a.n_idle == a.lifetime + (a.cause != "censored")
    assert a.cause in {"starvation", "predator", "toxin", "censored"}


def test_native_clock_holds_t_sim_against_the_deadline():
    class SlowSim(RandomArbiter):
        name = "slow_sim"

        def policy(self, obs):
            return {Action.ESCAPE: 1.0}, {"t_sim_ms": 50.0}

    cfg = CFG.model_copy(update={"deadline_ms": 10.0, "p_threat": 0.0, "max_trials": 5})
    native = run_episode(Arena(cfg), SlowSim(), 1, clock="native")
    wall = run_episode(Arena(cfg), SlowSim(), 1, clock="wall")
    assert native.n_missed_deadline == 5 and native.n_idle == 5 and native.n_escape == 0
    assert wall.n_missed_deadline == 0 and wall.n_escape == 5
