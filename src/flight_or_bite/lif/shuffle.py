"""Degree- and sign-preserving shuffle of the connectome (SPEC §4.2).

Targets are permuted among edges, separately for excitatory and inhibitory edges. This keeps,
for every neuron: its out-degree, its sign (a property of the presynaptic neuron), its synapse
counts per outgoing edge, and its excitatory and inhibitory in-degree. What is destroyed is
*who* connects to whom. Self-loops created by the permutation are removed by further swaps
within the same sign class.
"""

from __future__ import annotations

import numpy as np

from flight_or_bite.lif.graph import Connectome, from_edges


def shuffled(connectome: Connectome, seed: int, *, max_passes: int = 50) -> Connectome:
    rng = np.random.default_rng(seed)
    pre = connectome.pre()
    post = connectome.post.copy()
    count = connectome.count
    for mask in (count > 0, count < 0):
        idx = np.flatnonzero(mask)
        post[idx] = post[idx][rng.permutation(len(idx))]
        for _ in range(max_passes):  # repair self-loops by swapping targets within the class
            loops = idx[pre[idx] == post[idx]]
            if not len(loops):
                break
            partners = rng.choice(idx, size=len(loops))
            post[loops], post[partners] = post[partners].copy(), post[loops].copy()
    return from_edges(connectome.version, connectome.ids, pre, post, count)
