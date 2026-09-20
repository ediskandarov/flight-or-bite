"""Preregistration guard (SPEC §8): the test split opens only if PREREG.md is frozen and every
file hash listed in it matches the file on disk."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

PREREG = Path("PREREG.md")
STATUS_FROZEN = "Status: FROZEN"
STATUS_LINE = re.compile(
    r"^Status: FROZEN$", re.MULTILINE
)  # a line of its own, not a mention in prose
HASH_ROW = re.compile(r"^\| `([^`]+)` \| `([0-9a-f]{64})` \|$", re.MULTILINE)


class PreregError(PermissionError):
    pass


def hashed_files() -> list[Path]:
    return sorted([*Path("configs").glob("*.yaml"), *Path("configs/jev_prompts").glob("*.yaml"),
                   Path("data/circuits.yaml")])  # fmt: skip


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_table() -> str:
    rows = "\n".join(f"| `{f}` | `{sha256(f)}` |" for f in hashed_files())
    return "| Файл | SHA-256 |\n|---|---|\n" + rows


def check(path: Path | None = None) -> None:
    """Raise unless the preregistration is frozen and its hashes match the working tree."""
    path = path or PREREG
    if not path.is_file():
        raise PreregError("the test split stays locked until PREREG.md is committed (SPEC §8)")
    text = path.read_text()
    if not STATUS_LINE.search(text):
        raise PreregError(
            f"{path} is not frozen (no '{STATUS_FROZEN}' line); the test split stays locked"
        )
    listed = dict(HASH_ROW.findall(text))
    if not listed:
        raise PreregError(f"{path} lists no file hashes")
    missing = [str(f) for f in hashed_files() if str(f) not in listed]
    changed = [
        name
        for name, digest in listed.items()
        if not Path(name).is_file() or sha256(Path(name)) != digest
    ]
    if missing or changed:
        raise PreregError(
            f"preregistered hashes do not match: changed {changed}, not listed {missing}"
        )
