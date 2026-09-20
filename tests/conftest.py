"""Safety net: no test may reach a real API or spend money, even with keys in .env."""

import pytest

from flight_or_bite.arbiters.jev_client import API_KEY_ENV


@pytest.fixture(autouse=True)
def no_real_credentials(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.setattr("flight_or_bite.cli.app._load_env", lambda: None)


@pytest.fixture(autouse=True)
def raw_log_in_tmp(monkeypatch, tmp_path):
    """Tests must not write into the project's runs/ directory."""
    monkeypatch.setattr("flight_or_bite.arbiters.jev_client.DEFAULT_LOG_DIR", tmp_path / "jev_raw")
    monkeypatch.setattr("flight_or_bite.arbiters.jev_client.DEFAULT_LEDGER", tmp_path / "ledger.json")
