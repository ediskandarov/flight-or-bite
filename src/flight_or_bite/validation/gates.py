"""Validity gates (SPEC §5). Each gate writes reports/gates/<gate>.json."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GateResult:
    gate: str
    passed: bool
    metric: float
    threshold: float
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
