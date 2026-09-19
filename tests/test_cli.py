"""CLI skeleton: all SPEC §9 commands registered, stubs fail loudly, smoke test on the mock."""

import pytest
from typer.testing import CliRunner

from flight_or_bite.cli.app import EXIT_NOT_IMPLEMENTED, app

runner = CliRunner()

SPEC_COMMANDS = [
    ["fetch-data"],
    ["perf"],
    ["gate", "G1"],
    ["gates"],
    ["table", "build", "--arbiter", "connectome"],
    ["table", "show", "--arbiter", "jev", "--slice", "looming"],
    ["latency", "bench", "--arbiter", "all", "--n", "1000"],
    ["latency", "show"],
    ["live", "--seed", "1"],
    ["eval", "--split", "dev"],
    ["eval", "--split", "test", "--unlock-test", "--deadline-sweep"],
    ["replay", "--seed", "1", "--arbiter", "jev"],
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
    assert "p50" in result.output and "budget used 5/" in result.output


def test_jev_smoke_respects_max_calls():
    result = runner.invoke(app, ["jev", "smoke", "--mock", "--n", "5", "--mock-latency-ms", "0",
                                 "--max-calls", "3"])  # fmt: skip
    assert result.exit_code == 1
    assert "call budget exhausted" in result.output


def test_jev_smoke_without_key_explains():
    result = runner.invoke(app, ["jev", "smoke"])
    assert result.exit_code == 1
    assert "JEV_API_KEY" in result.output and "OPENROUTER_API_KEY" in result.output
