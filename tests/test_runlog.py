"""Run provenance survives multiple starts with the same clock timestamp."""

import json
from datetime import datetime
from types import SimpleNamespace

from flight_or_bite import runlog


def test_same_timestamp_keeps_each_runs_metadata(tmp_path, monkeypatch):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 5, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(runlog, "datetime", FrozenDatetime)
    monkeypatch.setattr(runlog, "_git", lambda *args: None)
    monkeypatch.setattr(runlog, "_versions", lambda: {})
    monkeypatch.setattr(runlog.sysinfo, "collect", lambda: SimpleNamespace(as_dict=lambda: {}))

    paths = [runlog.start_run("online-dev", {"attempt": i}, seeds=[i], root=tmp_path) for i in range(3)]

    assert len(set(paths)) == 3
    for i, path in enumerate(paths):
        meta = json.loads((path / "meta.json").read_text())
        assert meta["config"] == {"attempt": i}
        assert meta["seeds"] == [i]
