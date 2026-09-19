"""Safety net: no test may reach a real API or spend money, even with keys in .env."""

import pytest

from flight_or_bite.arbiters.jev_client import BACKENDS


@pytest.fixture(autouse=True)
def no_real_credentials(monkeypatch):
    for backend in BACKENDS.values():
        for var in backend.api_key_env:
            monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("flight_or_bite.cli.app._load_env", lambda: None)
