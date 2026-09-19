"""Safety net: no test may reach a real API or spend money, even with keys in .env."""

import pytest

from flight_or_bite.arbiters.jev_client import API_KEY_ENV


@pytest.fixture(autouse=True)
def no_real_credentials(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.setattr("flight_or_bite.cli.app._load_env", lambda: None)
