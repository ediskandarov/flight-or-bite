"""Oracle: Bayes posterior, value iteration checked against brute force on a toy MDP."""

from functools import cache

import numpy as np
import pytest

from flight_or_bite.arbiters.baselines import FixedPriorityArbiter, RandomArbiter
from flight_or_bite.arbiters.oracle import OracleArbiter, is_toxic, threat_posterior
from flight_or_bite.arena.env import Gaussian, load_env_config
from flight_or_bite.eval.episodes import run_split
from flight_or_bite.eval.stats import paired_bootstrap
from flight_or_bite.types import Action, Observation

CFG = load_env_config()


def test_posterior_equals_the_prior_where_the_likelihoods_cross():
    assert threat_posterior(0.45, CFG) == pytest.approx(CFG.p_threat)  # midpoint of 0.2 and 0.7


def test_posterior_rises_with_looming_and_uses_point_masses_at_the_ends():
    grid = np.linspace(0.001, 0.999, 200)
    post = [threat_posterior(float(x), CFG) for x in grid]
    assert np.all(np.diff(post) > 0) and post[0] < 0.02 and post[-1] > 0.95
    assert 0 < threat_posterior(0.0, CFG) < 0.02 and 0.95 < threat_posterior(1.0, CFG) < 1


def test_toxicity_is_read_exactly_from_bitter():
    assert is_toxic(Observation(0.5, 0.3, 0.0, 0.5), CFG)
    assert not is_toxic(Observation(0.5, 0.1, 0.0, 0.5), CFG)
    assert not is_toxic(Observation(0.0, 0.9, 0.0, 0.5), CFG)  # no food, nothing to be toxic


def toy_config():
    """Threat is revealed by looming; food is always sugar 0.5; all energy steps are multiples
    of 0.5, so the oracle's energy grid represents every reachable state exactly."""
    return CFG.model_copy(update=dict(
        max_trials=4, energy_start=3.0, p_food=0.5, p_toxic=0.0, sugar_range=(0.5, 0.5),
        p_threat=0.5, looming_threat=Gaussian(mean=0.9, sd=1e-4),
        looming_safe=Gaussian(mean=0.1, sd=1e-4),
    ))  # fmt: skip


def brute_force_value(cfg, energy: float) -> float:
    gain = cfg.eat_gain * cfg.sugar_range[0]

    def alive(e: float, t: int) -> float:
        e = min(e, cfg.energy_max)
        return 0.0 if e <= 0 else 1.0 + value(t + 1, e)

    @cache
    def value(t: int, e: float) -> float:
        if t == cfg.max_trials:
            return 0.0
        total = 0.0
        for p_food, g in ((cfg.p_food, gain), (1 - cfg.p_food, 0.0)):
            for p_thr, threat in ((cfg.p_threat, 1.0), (1 - cfg.p_threat, 0.0)):
                q = max(
                    (1 - threat * cfg.p_death_eat) * alive(e - cfg.metabolism + g, t),
                    alive(e - cfg.metabolism - cfg.escape_cost, t),
                    (1 - threat * cfg.p_death_idle) * alive(e - cfg.metabolism, t),
                )
                total += p_food * p_thr * q
        return total

    return value(0, energy)


def test_value_iteration_matches_brute_force_on_a_toy_mdp():
    cfg = toy_config()
    oracle = OracleArbiter(cfg, n_sugar=1, n_bitter=1, n_looming=10)
    for energy in (1.0, 3.0, 4.5, 10.0):
        expected = brute_force_value(cfg, energy)
        got = float(np.interp(energy, oracle.energy_grid, oracle.values[0]))
        assert got == pytest.approx(expected, abs=1e-9), energy
    assert 0 < brute_force_value(cfg, 1.0) < brute_force_value(cfg, 10.0) <= cfg.max_trials


def test_value_is_monotone_in_energy_and_zero_when_dead():
    oracle = OracleArbiter(CFG)
    assert oracle.values[0][0] == 0.0
    assert np.all(np.diff(oracle.values[0]) >= -1e-9)
    assert np.all(oracle.values[-1] == 0.0)


def test_oracle_choices_in_clear_cases():
    oracle = OracleArbiter(CFG)

    def act(**kw):
        probs, _ = oracle.policy(Observation(**kw))
        return max(probs, key=probs.__getitem__)

    assert act(sugar=0.9, bitter=0.0, looming=0.0, hunger=0.5) is Action.EAT
    assert act(sugar=0.9, bitter=0.0, looming=1.0, hunger=0.5) is Action.ESCAPE
    assert act(sugar=0.3, bitter=0.9, looming=0.0, hunger=0.2) is not Action.EAT  # net loss
    assert act(sugar=0.0, bitter=0.0, looming=0.0, hunger=0.5) is Action.IDLE
    decision = oracle.decide(Observation(0.9, 0.0, 0.0, 0.5), np.random.default_rng(0))
    assert decision.action is Action.EAT and decision.t_wall_ns > 0 and decision.t_sim_ms is None
    assert 0 <= decision.meta["p_threat"] <= 1 and set(decision.meta["q"]) == {
        "EAT",
        "ESCAPE",
        "IDLE",
    }


def test_oracle_never_escapes_in_a_world_without_threats():
    calm = CFG.model_copy(update={"p_threat": 0.0, "max_trials": 100})
    results = run_split(calm, OracleArbiter(calm), range(5000, 5010))
    assert sum(r.n_escape for r in results) == 0


def test_oracle_beats_both_baselines_on_paired_seeds():
    seeds = range(5000, 5150)  # outside dev and test
    life = {
        arb.name: np.array([r.lifetime for r in run_split(CFG, arb, seeds)])
        for arb in (RandomArbiter(), FixedPriorityArbiter(), OracleArbiter(CFG))
    }
    rng = np.random.default_rng(0)
    for baseline in ("random", "fixed_priority"):
        diff = paired_bootstrap(life["oracle"], life[baseline], rng, n=2000)
        assert diff.significant and diff.ci_low > 0, baseline
    assert life["fixed_priority"].mean() > life["random"].mean()


def test_exact_ties_go_to_the_cheapest_action():
    """With no threats and energy to spare the value saturates and Q(IDLE) == Q(ESCAPE)."""
    calm = CFG.model_copy(update={"p_threat": 0.0, "max_trials": 50})
    oracle = OracleArbiter(calm)
    obs = Observation(sugar=0.0, bitter=0.0, looming=0.3, hunger=0.0)
    q = oracle.q_values(obs)
    assert q[Action.IDLE] == q[Action.ESCAPE] == q[Action.EAT]
    probs, _ = oracle.policy(obs)
    assert probs[Action.IDLE] == 1.0
