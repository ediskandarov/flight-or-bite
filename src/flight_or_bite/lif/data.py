"""Download and verify the connectome files listed in configs/data.yaml (SPEC §9 fetch-data)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Literal

import httpx
import yaml
from pydantic import BaseModel

CHUNK = 1 << 20


class DataSource(BaseModel):
    repo: str
    commit: str
    code_license: str
    data_license: str


class DataFile(BaseModel):
    name: str
    version: int
    role: Literal["connectivity", "completeness"]
    bytes: int
    git_blob_sha1: str


class DataManifest(BaseModel):
    source: DataSource
    files: list[DataFile]

    def for_version(self, version: int) -> dict[str, DataFile]:
        """role -> file for one connectome version."""
        found = {f.role: f for f in self.files if f.version == version}
        if set(found) != {"connectivity", "completeness"}:
            raise ValueError(f"manifest has no complete file pair for version {version}")
        return found

    def url(self, file: DataFile) -> str:
        return (
            f"https://raw.githubusercontent.com/{self.source.repo}/{self.source.commit}/{file.name}"
        )


class ChecksumError(Exception):
    pass


def load_manifest(path: Path) -> DataManifest:
    return DataManifest.model_validate(yaml.safe_load(path.read_text()))


def git_blob_sha1(path: Path) -> str:
    """SHA-1 as git computes it for a blob: sha1(b"blob <size>\\0" + content)."""
    h = hashlib.sha1(f"blob {path.stat().st_size}\0".encode(), usedforsecurity=False)
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def is_valid(path: Path, file: DataFile) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == file.bytes
        and git_blob_sha1(path) == file.git_blob_sha1
    )


def fetch_file(
    manifest: DataManifest,
    file: DataFile,
    dest_dir: Path,
    client: httpx.Client,
    on_bytes: Callable[[int], None] = lambda n: None,
) -> tuple[Path, bool]:
    """Ensure dest_dir/file.name exists and matches the manifest. Returns (path, downloaded)."""
    target = dest_dir / file.name
    if is_valid(target, file):
        return target, False

    dest_dir.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    with client.stream("GET", manifest.url(file), follow_redirects=True) as resp:
        resp.raise_for_status()
        with part.open("wb") as out:
            for chunk in resp.iter_bytes(CHUNK):
                out.write(chunk)
                on_bytes(len(chunk))
    if not is_valid(part, file):
        got = f"{part.stat().st_size} bytes, git blob sha1 {git_blob_sha1(part)}"
        part.unlink()
        raise ChecksumError(
            f"{file.name}: expected {file.bytes} bytes, {file.git_blob_sha1}; got {got}"
        )
    part.replace(target)  # atomic: a half-written file never carries the real name
    return target, True


def select(manifest: DataManifest, versions: Iterable[int]) -> list[DataFile]:
    wanted = set(versions)
    unknown = wanted - {f.version for f in manifest.files}
    if unknown:
        raise ValueError(f"unknown connectome version(s): {sorted(unknown)}")
    return [f for f in manifest.files if f.version in wanted]
