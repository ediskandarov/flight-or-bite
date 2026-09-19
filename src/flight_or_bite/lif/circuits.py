"""Named neuron sets from data/circuits.yaml, resolved against one connectome version."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict

from flight_or_bite.lif.graph import Connectome


class CircuitSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    provenance: str
    verified: dict[int, str]
    absent_in: dict[int, list[int]] = {}
    ids: list[int]


def load_circuits(path: Path = Path("data/circuits.yaml")) -> dict[str, CircuitSet]:
    raw = yaml.safe_load(path.read_text())
    return {name: CircuitSet.model_validate(body) for name, body in raw.items()}


def resolve(connectome: Connectome, circuit: CircuitSet) -> np.ndarray:
    """Model indices of a set. Only ids declared absent for this version may be missing."""
    version = connectome.version
    if version not in circuit.verified:
        raise KeyError(f"circuit set is not verified for connectome v{version}")
    absent = set(circuit.absent_in.get(version, []))
    return connectome.index_of([i for i in circuit.ids if i not in absent])
