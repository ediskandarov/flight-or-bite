"""Environment: determinism, energy dynamics, causes of death, deadline, locked test split."""

import numpy as np
import pytest

from flight_or_bite.arena import env as env_module
from flight_or_bite.arena.env import Arena, SplitLocked, load_env_config
from flight_or_bite.types import Action

CFG = load_env_config()


def cfg(**changes):
    return CFG.model_copy(update=changes)


def test_config_is_the_spec_with_the_authors_three_changes():
    assert (CFG.energy_start, CFG.energy_max, CFG.max_trials) == (50.0, 100.0, 500)
    assert (CFG.p_toxic, CFG.p_threat, CFG.toxic_cost, CFG.metabolism) == (0.25, 0.2, 15.0, 1.0)
    assert (CFG.p_food, CFG.eat_gain, CFG.escape_cost) == (0.3, 8.0, 1.0)  # decision D31
    assert (CFG.p_death_eat, CFG.p_death_idle) == (0.6, 0.3)
    assert CFG.deadline_ms is None
    assert list(CFG.seeds_of("dev"))[::999] == [0, 999] and CFG.split_of(100_500) == "test"
    assert CFG.split_of(5000) is None


def test_world_is_identical_for_different_policies_on_one_seed():
    calm = cfg(p_threat=0.0)
    seen = {}
    for action in (Action.IDLE, Action.ESCAPE):
        arena = Arena(calm)
        obs, rows = arena.reset(7), []
        for _ in range(10):
            rows.append((obs.sugar, obs.bitter, obs.looming))
            obs, done, _ = arena.step(action)
            assert not done
        seen[action] = rows
    assert seen[Action.IDLE] == seen[Action.ESCAPE]
    assert Arena(calm).reset(7) == Arena(calm).reset(7) != Arena(calm).reset(8)


def test_stimulus_distributions():
    arena = Arena(CFG)
    arena.reset(3)
    food = arena.sugar > 0
    assert np.all((arena.sugar[food] >= 0.2) & (arena.sugar[food] <= 1.0))
    assert not np.any(arena.toxic & ~food)  # only food can be toxic
    assert np.all(arena.bitter[arena.toxic] >= 0.3) and np.all(arena.bitter[~arena.toxic] <= 0.1)
    assert np.all((arena.looming >= 0) & (arena.looming <= 1))
    assert arena.looming[arena.threat].mean() > arena.looming[~arena.threat].mean() + 0.3
    assert abs(food.mean() - CFG.p_food) < 0.1 and 0.12 < arena.threat.mean() < 0.28


def test_idle_starves_after_the_energy_runs_out():
    arena = Arena(cfg(p_threat=0.0))
    obs = arena.reset(1)
    assert obs.hunger == pytest.approx(0.5)
    done, info, steps = False, {}, 0
    while not done:
        obs, done, info = arena.step(Action.IDLE)
        steps += 1
    # 50 energy, -1 per trial: alive after 49 trials, energy hits 0 on the 50th
    assert (steps, info["lifetime"], info["cause"]) == (50, 49, "starvation")


def test_escape_costs_its_price_plus_metabolism():
    arena = Arena(cfg(p_threat=0.0))
    arena.reset(1)
    obs, _, info = arena.step(Action.ESCAPE)
    expected = 50.0 - CFG.metabolism - CFG.escape_cost
    assert info["energy"] == pytest.approx(expected) and obs.hunger == pytest.approx(
        1 - expected / 100
    )


def test_eating_gains_energy_and_is_capped():
    sweet = cfg(p_threat=0.0, p_food=1.0, p_toxic=0.0, sugar_range=(1.0, 1.0), energy_start=95.0)
    arena = Arena(sweet)
    arena.reset(1)
    _, _, info = arena.step(Action.EAT)
    assert info["energy"] == 100.0  # 95 - 1 + 12, capped


def test_toxic_food_kills_with_cause_toxin():
    poison = cfg(p_threat=0.0, p_food=1.0, p_toxic=1.0, sugar_range=(0.2, 0.2),
                 bitter_toxic_range=(1.0, 1.0), energy_start=5.0)  # fmt: skip
    arena = Arena(poison)
    arena.reset(1)
    _, done, info = arena.step(Action.EAT)  # 5 - 1 + 2.4 - 15 < 0
    assert done and info["cause"] == "toxin" and info["lifetime"] == 0 and info["toxic"]


def test_predator_kills_unless_the_agent_escapes():
    deadly = cfg(p_threat=1.0, p_death_idle=1.0, p_death_eat=1.0)
    for action in (Action.IDLE, Action.EAT):
        arena = Arena(deadly)
        arena.reset(1)
        _, done, info = arena.step(action)
        assert done and info["cause"] == "predator" and info["lifetime"] == 0 and info["threat"]
    arena = Arena(deadly)
    arena.reset(1)
    _, done, _ = arena.step(Action.ESCAPE)
    assert not done


def test_deadline_replaces_a_late_action_with_idle():
    deadly = cfg(p_threat=1.0, p_death_idle=1.0, deadline_ms=10.0)
    arena = Arena(deadly)
    arena.reset(1)
    _, done, info = arena.step(Action.ESCAPE, decision_time_ms=5.0)
    assert not done and not info["missed_deadline"] and info["action"] is Action.ESCAPE
    _, done, info = arena.step(Action.ESCAPE, decision_time_ms=10.5)
    assert done and info["missed_deadline"] and info["action"] is Action.IDLE
    assert info["cause"] == "missed_deadline"


def test_deadline_is_off_by_default():
    arena = Arena(cfg(p_threat=1.0, p_death_idle=1.0))
    arena.reset(1)
    _, done, info = arena.step(Action.ESCAPE, decision_time_ms=1e9)
    assert not done and not info["missed_deadline"]


def test_survivors_are_censored_at_max_trials():
    arena = Arena(cfg(p_threat=0.0, max_trials=5))
    arena.reset(1)
    for _ in range(4):
        _, done, _ = arena.step(Action.IDLE)
        assert not done
    _, done, info = arena.step(Action.IDLE)
    assert done and info["cause"] == "censored" and info["lifetime"] == 5
    with pytest.raises(RuntimeError):
        arena.step(Action.IDLE)


def test_test_split_is_locked_logged_and_needs_prereg(tmp_path, monkeypatch):
    monkeypatch.setattr(env_module, "TEST_ACCESS_LOG", tmp_path / "test_access.log")
    monkeypatch.setattr(env_module, "PREREG", tmp_path / "PREREG.md")
    with pytest.raises(SplitLocked, match="unlock-test"):
        Arena(CFG).reset(100_000)
    with pytest.raises(SplitLocked, match="PREREG"):
        Arena(CFG, unlock_test=True).reset(100_000)
    assert not (tmp_path / "test_access.log").exists()

    (tmp_path / "PREREG.md").write_text("# prereg")
    Arena(CFG, unlock_test=True).reset(100_000)
    Arena(CFG, unlock_test=True).reset(100_001)
    log = (tmp_path / "test_access.log").read_text().splitlines()
    assert len(log) == 2 and "seed=100000" in log[0] and "seed=100001" in log[1]
    Arena(CFG).reset(999)  # dev needs no unlock and is not logged
    assert len((tmp_path / "test_access.log").read_text().splitlines()) == 2
