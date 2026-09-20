"""The connectome as a CSR graph keyed by presynaptic neuron (SPEC §4.1: the whole graph)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from flight_or_bite.lif.data import DataManifest

WEIGHT_COLUMN = "Excitatory x Connectivity"  # signed synapse count, as used by model.py


@dataclass(frozen=True)
class Connectome:
    """Edges of neuron i are post[indptr[i]:indptr[i+1]] with signed synapse counts `count`."""

    version: int
    ids: np.ndarray  # int64 FlyWire root ids; position = model index (same as model.py)
    indptr: np.ndarray  # int64, len n + 1
    post: np.ndarray  # int32
    count: np.ndarray  # int32, signed: excitatory > 0, inhibitory < 0

    @property
    def n_neurons(self) -> int:
        return len(self.ids)

    @property
    def n_edges(self) -> int:
        return len(self.post)

    def pre(self) -> np.ndarray:
        """Presynaptic index of every edge (expands indptr)."""
        return np.repeat(np.arange(self.n_neurons, dtype=np.int32), np.diff(self.indptr))

    def index_of(self, root_ids: list[int] | np.ndarray) -> np.ndarray:
        """Model indices of FlyWire root ids. Unknown ids are an error, never skipped."""
        root_ids = np.asarray(root_ids, dtype=np.int64)
        order = np.argsort(self.ids)
        pos = np.searchsorted(self.ids, root_ids, sorter=order).clip(max=self.n_neurons - 1)
        found = order[pos]
        missing = root_ids[self.ids[found] != root_ids]
        if missing.size:
            raise KeyError(
                f"root ids not in connectome v{self.version}: {missing.tolist()} "
                "(root ids change between materialisations)"
            )
        return found.astype(np.int32)

    def present(self, root_ids: list[int] | np.ndarray) -> np.ndarray:
        return np.isin(np.asarray(root_ids, dtype=np.int64), self.ids)


def from_edges(version: int, ids: np.ndarray, pre: np.ndarray, post: np.ndarray, count: np.ndarray) -> Connectome:
    n = len(ids)
    if pre.size and (min(pre.min(), post.min()) < 0 or max(pre.max(), post.max()) >= n):
        raise ValueError("edge index outside the neuron table")
    order = np.argsort(pre, kind="stable")
    indptr = np.zeros(n + 1, dtype=np.int64)
    np.cumsum(np.bincount(pre, minlength=n), out=indptr[1:])
    return Connectome(
        version=version,
        ids=np.asarray(ids, dtype=np.int64),
        indptr=indptr,
        post=post[order].astype(np.int32),
        count=count[order].astype(np.int32),
    )


def load_connectome(manifest: DataManifest, version: int, data_dir: Path) -> Connectome:
    files = manifest.for_version(version)
    ids = pd.read_csv(data_dir / files["completeness"].name, index_col=0).index.to_numpy()
    edges = pd.read_parquet(
        data_dir / files["connectivity"].name,
        columns=["Presynaptic_Index", "Postsynaptic_Index", WEIGHT_COLUMN],
    )
    return from_edges(
        version,
        ids,
        edges["Presynaptic_Index"].to_numpy(),
        edges["Postsynaptic_Index"].to_numpy(),
        edges[WEIGHT_COLUMN].to_numpy(),
    )
