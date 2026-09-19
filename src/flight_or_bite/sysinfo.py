"""Host description logged at start-up (SPEC §10): chip, core counts, memory."""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SystemInfo:
    chip: str
    machine: str
    os_version: str
    python: str
    performance_cores: int | None
    efficiency_cores: int | None
    logical_cores: int | None
    memory_gb: float | None

    @property
    def default_workers(self) -> int:
        """Default parallelism = performance cores (timing runs always use one process)."""
        return self.performance_cores or self.logical_cores or 1

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _sysctl(key: str) -> str | None:
    try:
        out = subprocess.run(
            ["sysctl", "-n", key], capture_output=True, text=True, timeout=5, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def _sysctl_int(key: str) -> int | None:
    value = _sysctl(key)
    return int(value) if value and value.isdigit() else None


def collect() -> SystemInfo:
    memsize = _sysctl_int("hw.memsize")
    return SystemInfo(
        chip=_sysctl("machdep.cpu.brand_string") or platform.processor() or "unknown",
        machine=platform.machine(),
        os_version=f"{platform.system()} {platform.release()}",
        python=platform.python_version(),
        performance_cores=_sysctl_int("hw.perflevel0.physicalcpu"),
        efficiency_cores=_sysctl_int("hw.perflevel1.physicalcpu"),
        logical_cores=os.cpu_count(),
        memory_gb=round(memsize / 2**30, 1) if memsize else None,
    )
