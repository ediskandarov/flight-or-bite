"""Connectome download: manifest, git-blob checksums, atomic verified fetch."""

import hashlib
from pathlib import Path

import httpx
import pytest

from flight_or_bite.lif.data import (
    ChecksumError,
    DataFile,
    DataManifest,
    DataSource,
    fetch_file,
    git_blob_sha1,
    is_valid,
    load_manifest,
    select,
)

CONTENT = b"pre,post,weight\n" * 1000
BLOB_SHA1 = hashlib.sha1(b"blob %d\0" % len(CONTENT) + CONTENT).hexdigest()
FILE = DataFile(name="toy.csv", version=1, role="completeness", bytes=len(CONTENT), git_blob_sha1=BLOB_SHA1)
MANIFEST = DataManifest(
    source=DataSource(repo="o/r", commit="abc", code_license="MIT", data_license="CC BY-NC 4.0"),
    files=[FILE],
)


def client_serving(body: bytes, seen: list | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(str(request.url))
        return httpx.Response(200, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_git_blob_sha1_matches_git(tmp_path):
    path = tmp_path / "hello"
    path.write_bytes(b"hello\n")
    assert git_blob_sha1(path) == "ce013625030ba8dba906f756967f9e9ca394464a"  # git hash-object


def test_fetch_downloads_verifies_and_caches(tmp_path):
    seen: list[str] = []
    progress: list[int] = []
    with client_serving(CONTENT, seen) as client:
        path, downloaded = fetch_file(MANIFEST, FILE, tmp_path, client, progress.append)
        assert downloaded and path.read_bytes() == CONTENT
        assert sum(progress) == len(CONTENT)
        assert seen == ["https://raw.githubusercontent.com/o/r/abc/toy.csv"]
        _, downloaded_again = fetch_file(MANIFEST, FILE, tmp_path, client)
    assert not downloaded_again and len(seen) == 1
    assert not list(tmp_path.glob("*.part"))


def test_corrupt_download_is_rejected_and_leaves_nothing(tmp_path):
    with client_serving(CONTENT[:-1] + b"X") as client:
        with pytest.raises(ChecksumError):
            fetch_file(MANIFEST, FILE, tmp_path, client)
    assert list(tmp_path.iterdir()) == []


def test_corrupt_local_file_is_replaced(tmp_path):
    (tmp_path / FILE.name).write_bytes(b"truncated")
    assert not is_valid(tmp_path / FILE.name, FILE)
    with client_serving(CONTENT) as client:
        path, downloaded = fetch_file(MANIFEST, FILE, tmp_path, client)
    assert downloaded and is_valid(path, FILE)


def test_project_manifest_is_consistent():
    manifest = load_manifest(Path(__file__).parents[1] / "configs" / "data.yaml")
    assert len(manifest.source.commit) == 40
    for version in (630, 783):
        pair = manifest.for_version(version)
        assert pair["connectivity"].name.endswith(".parquet")
        assert pair["completeness"].name.endswith(".csv")
    assert all(len(f.git_blob_sha1) == 40 for f in manifest.files)
    with pytest.raises(ValueError):
        select(manifest, [999])
    with pytest.raises(ValueError):
        manifest.for_version(999)
