"""CLI skeleton: all SPEC §9 commands registered, stubs fail loudly, smoke test on the mock."""

import pytest
from typer.testing import CliRunner

from flight_or_bite.cli.app import EXIT_NOT_IMPLEMENTED, app

runner = CliRunner()

SPEC_COMMANDS = [
    ["latency", "bench", "--arbiter", "all", "--n", "1000"],
    ["latency", "show"],
    ["live", "--seed", "1"],
    ["report"],
]


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ("fetch-data", "perf", "gate", "gates", "table", "latency", "live", "eval",
                 "replay", "report", "jev", "info"):  # fmt: skip
        assert name in result.output


@pytest.mark.parametrize("argv", SPEC_COMMANDS, ids=" ".join)
def test_spec_commands_parse_and_report_not_implemented(argv):
    result = runner.invoke(app, argv)
    assert result.exit_code == EXIT_NOT_IMPLEMENTED, result.output
    assert "not implemented" in result.output


def test_invalid_arbiter_is_a_usage_error():
    result = runner.invoke(app, ["table", "build", "--arbiter", "bogus"])
    assert result.exit_code == 2  # click usage error, distinct from EXIT_NOT_IMPLEMENTED


def test_info():
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "default_workers" in result.output


def test_jev_smoke_on_mock():
    result = runner.invoke(app, ["jev", "smoke", "--mock", "--n", "5", "--mock-latency-ms", "1"])
    assert result.exit_code == 0, result.output
    assert "p50" in result.output and "p95" in result.output and "budget used 5/" in result.output


def test_jev_smoke_respects_max_calls():
    result = runner.invoke(app, ["jev", "smoke", "--mock", "--n", "5", "--mock-latency-ms", "0",
                                 "--max-calls", "3"])  # fmt: skip
    assert result.exit_code == 1
    assert "call budget exhausted" in result.output


def test_jev_smoke_without_key_explains():
    result = runner.invoke(app, ["jev", "smoke"])
    assert result.exit_code == 1
    assert "OPENROUTER_API_KEY" in result.output


def test_eval_refuses_the_test_split_without_unlock():
    result = runner.invoke(app, ["eval", "--split", "test"])
    assert result.exit_code == 1 and "unlock-test" in result.output


def test_eval_refuses_the_test_split_without_prereg(monkeypatch, tmp_path):
    monkeypatch.setattr("flight_or_bite.prereg.PREREG", tmp_path / "PREREG.md")
    result = runner.invoke(app, ["eval", "--split", "test", "--unlock-test"])
    assert result.exit_code == 1 and "PREREG" in result.output


def test_table_build_show_and_replay(tmp_path, monkeypatch):
    monkeypatch.setattr("flight_or_bite.policy_table.cli_ops.TABLE_ROOT", tmp_path)
    grid = tmp_path / "grid.yaml"
    grid.write_text(
        "axes:\n  sugar: [0.0, 1.0]\n  bitter: [0.0, 1.0]\n  looming: [0.0, 0.5, 1.0]\n"
        "  hunger: [0.0, 1.0]\nn_rep: 2\nshard_points: 10\nseed_base: 1\n"
    )
    built = runner.invoke(
        app, ["table", "build", "--arbiter", "fixed_priority", "--grid", str(grid)]
    )
    assert built.exit_code == 0 and "48 new decisions" in built.output, built.output
    again = runner.invoke(
        app, ["table", "build", "--arbiter", "fixed_priority", "--grid", str(grid)]
    )
    assert "0 new decisions" in again.output

    shown = runner.invoke(
        app, ["table", "show", "--arbiter", "fixed_priority", "--slice", "looming"]
    )
    assert shown.exit_code == 0 and "p_escape" in shown.output and "1.000" in shown.output

    played = runner.invoke(app, ["replay", "--seed", "3", "--arbiter", "fixed_priority"])
    assert (
        played.exit_code == 0
        and "fixed_priority_table" in played.output
        and "end:" in played.output
    )


def test_jev_table_on_the_mock_needs_a_mode(tmp_path, monkeypatch):
    monkeypatch.setattr("flight_or_bite.policy_table.cli_ops.TABLE_ROOT", tmp_path)
    missing = runner.invoke(app, ["table", "build", "--arbiter", "jev", "--mock"])
    assert missing.exit_code == EXIT_NOT_IMPLEMENTED and "--mode" in missing.output


def test_connectome_tables_wait_for_the_decoder_and_missing_tables_are_explained(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("flight_or_bite.policy_table.cli_ops.TABLE_ROOT", tmp_path)
    for name in ("connectome", "shuffled"):
        result = runner.invoke(app, ["table", "build", "--arbiter", name])
        assert result.exit_code == EXIT_NOT_IMPLEMENTED and "decoder" in result.output
    result = runner.invoke(app, ["table", "show", "--arbiter", "jev_naive"])
    assert result.exit_code == EXIT_NOT_IMPLEMENTED and "fob table build" in result.output


def test_replay_plays_a_baseline_directly_when_there_is_no_table(tmp_path, monkeypatch):
    monkeypatch.setattr("flight_or_bite.policy_table.cli_ops.TABLE_ROOT", tmp_path)
    result = runner.invoke(app, ["replay", "--seed", "3", "--arbiter", "oracle"])
    assert result.exit_code == 0 and "arbiter oracle" in result.output and "end:" in result.output
