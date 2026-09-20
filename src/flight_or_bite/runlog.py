"""Per-run output directory (SPEC §10): config, git hash, seeds, versions, host, results."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from flight_or_bite import sysinfo

TRACKED_PACKAGES = (
    "flight-or-bite",
    "numpy",
    "numba",
    "brian2",
    "torch",
    "scipy",
    "pandas",
    "httpx",
)


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def _versions() -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for name in TRACKED_PACKAGES:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = None
    return found


def start_run(name: str, config: dict[str, Any], seeds: Any = None, root: Path = Path("runs")) -> Path:
    """Create runs/<timestamp>_<name>/ and write meta.json into it."""
    run_dir = root / f"{datetime.now().strftime('%Y%m%dT%H%M%S')}_{name}"
    run_dir.mkdir(parents=True, exist_ok=False)
    status = _git("status", "--porcelain")
    meta = {
        "name": name,
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
        "argv": sys.argv,
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(status) if status is not None else None,
        "config": config,
        "seeds": seeds,
        "versions": _versions(),
        "host": sysinfo.collect().as_dict(),
    }
    write_json(run_dir / "meta.json", meta)
    return run_dir


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")
