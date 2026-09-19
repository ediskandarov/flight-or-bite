"""Backend factory. Imports are lazy: Brian2 and PyTorch are slow to import."""

from __future__ import annotations

from flight_or_bite.lif.backend import LIFBackend
from flight_or_bite.lif.graph import Connectome
from flight_or_bite.lif.params import LIFParams

BACKEND_NAMES = ("brian2", "event", "torch-mps", "torch-cpu")


def make_backend(name: str, connectome: Connectome, params: LIFParams) -> LIFBackend:
    if name == "brian2":
        from flight_or_bite.lif.brian2_backend import Brian2Backend

        return Brian2Backend(connectome, params)
    if name == "event":
        from flight_or_bite.lif.event_backend import EventBackend

        return EventBackend(connectome, params)
    if name in ("torch-mps", "torch-cpu"):
        from flight_or_bite.lif.torch_backend import TorchBackend

        return TorchBackend(connectome, params, device=name.removeprefix("torch-"))
    raise ValueError(f"unknown backend {name!r}; expected one of {', '.join(BACKEND_NAMES)}")
