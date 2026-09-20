"""Main-metric runner: paired, resumable, and an unfinished episode is never written."""

import json

import pytest
from rich.console import Console

from flight_or_bite.arbiters.jev_client import JevHTTPError, MockJevClient
from flight_or_bite.eval import online

NAMES = ("jev_informed", "oracle", "random")
console = Console(quiet=True)


def lines(path):
    return [json.loads(x) for x in path.read_text().splitlines()] if path.is_file() else []


def test_run_is_paired_and_resumes_without_replaying_finished_episodes(tmp_path):
    out = online.run_online(console, "dev", 3, False, False, tmp_path / "o", NAMES, mock_jev=True)
    episodes = lines(out / "episodes.jsonl")
    assert sorted((e["arbiter"], e["seed"]) for e in episodes) == sorted((n, s) for n in NAMES for s in range(3))
    decisions = lines(out / "decisions.jsonl")
    for e in episodes:  # every finished episode has all of its decisions, including the fatal one
        n = sum(d["arbiter"] == e["arbiter"] and d["seed"] == e["seed"] for d in decisions)
        assert n == e["lifetime"] + (e["cause"] != "censored")
    online.run_online(console, "dev", 4, False, False, tmp_path / "o", NAMES, mock_jev=True)
    assert len(lines(out / "episodes.jsonl")) == len(episodes) + len(NAMES)  # only seed 3 was added
    s = online.summary_of(out)
    assert s["episodes"] == 4 and set(s["arbiters"]) == set(NAMES) and s["stops"] == []


def test_a_jev_failure_stops_the_run_and_discards_the_unfinished_episode(tmp_path, monkeypatch):
    calls = {"n": 0}
    real = MockJevClient.evaluate

    def flaky(self, state, questions):
        calls["n"] += 1
        if calls["n"] == 4:  # dies in the middle of an episode; 401 is not retried
            raise JevHTTPError(401, "bad key", None)
        return real(self, state, questions)

    monkeypatch.setattr(MockJevClient, "evaluate", flaky)
    with pytest.raises(online.RunStopped, match="re-run the same command"):
        online.run_online(console, "dev", 3, False, False, tmp_path / "o", NAMES, mock_jev=True)
    out = tmp_path / "o"
    broken = lines(out / "stops.jsonl")[0]
    assert broken["arbiter"] == "jev_informed" and "401" in broken["error"]
    assert not any(
        d["seed"] == broken["seed"] and d["arbiter"] == "jev_informed" for d in lines(out / "decisions.jsonl")
    )

    calls["n"] = 10**6  # the fault is fixed: the same command resumes and replays that episode
    online.run_online(console, "dev", 3, False, False, out, NAMES, mock_jev=True)
    assert len(lines(out / "episodes.jsonl")) == 9 and online.summary_of(out)["episodes"] == 3


def test_online_test_split_is_locked(tmp_path):
    from flight_or_bite.arena.env import SplitLocked

    with pytest.raises(SplitLocked):
        online.run_online(console, "test", 1, False, False, tmp_path / "o", NAMES, mock_jev=True)
    assert not (tmp_path / "o").exists()
