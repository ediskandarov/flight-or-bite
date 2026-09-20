"""LIF on PyTorch, for the Apple MPS device (SPEC §4.1, candidate 3).

Same step semantics and the same precomputed Poisson schedule as the event backend, so the two
can be compared spike for spike under one seed. Sparse tensors are avoided: spikes propagate
through `index_add_` over the CSR edge ranges of the neurons that fired. MPS has no float64, so
this backend runs in float32 and cannot be bit-identical to Brian2.
"""

from __future__ import annotations

import math
import time

import numpy as np
import torch

from flight_or_bite.lif.backend import Stimulus, StopOnFirstSpike, TrialResult
from flight_or_bite.lif.event_backend import poisson_schedule
from flight_or_bite.lif.graph import Connectome
from flight_or_bite.lif.params import LIFParams

NEVER = -(2**30)


class TorchBackend:
    def __init__(self, connectome: Connectome, params: LIFParams, *, device: str = "mps") -> None:
        t0 = time.perf_counter()
        if device == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS device is not available")
        self.name = f"torch-{device}"
        self.device = torch.device(device)
        self.dtype = torch.float32 if device == "mps" else torch.float64
        self.params = params
        self.n = connectome.n_neurons
        p = params
        self._a_v = math.exp(-p.dt_ms / p.t_mbr_ms)
        self._a_g = math.exp(-p.dt_ms / p.tau_ms)
        self._c_g = p.tau_ms / (p.tau_ms - p.t_mbr_ms) * (self._a_g - self._a_v)

        dev = self.device
        self._indptr = torch.from_numpy(connectome.indptr).to(dev)
        self._post = torch.from_numpy(connectome.post.astype(np.int64)).to(dev)
        self._w = torch.from_numpy(connectome.count * p.w_syn_mv).to(self.dtype).to(dev)
        self._sync()
        self.t_load_s = time.perf_counter() - t0

    def _sync(self) -> None:
        if self.device.type == "mps":
            torch.mps.synchronize()

    def run_trial(
        self,
        stimulus: Stimulus,
        t_max_ms: float,
        seed: int,
        stop: StopOnFirstSpike | None = None,
        silenced: np.ndarray | None = None,
        kicks: tuple[np.ndarray, np.ndarray] | None = None,
    ) -> TrialResult:
        t0 = time.perf_counter_ns()
        p, dev, n = self.params, self.device, self.n
        n_steps, delay = round(t_max_ms / p.dt_ms), p.delay_steps

        if kicks is None:
            kicks = poisson_schedule(stimulus, n_steps, p.dt_ms, np.random.default_rng(seed))
        kick_step, kick_neuron = kicks
        kick_ptr = np.zeros(n_steps + 1, dtype=np.int64)
        np.cumsum(np.bincount(kick_step[kick_step < n_steps], minlength=n_steps), out=kick_ptr[1:])
        kick_neuron_t = torch.from_numpy(kick_neuron.astype(np.int64)).to(dev)

        v = torch.full((n,), p.v_0_mv, dtype=self.dtype, device=dev)
        g = torch.zeros(n, dtype=self.dtype, device=dev)
        last = torch.full((n,), NEVER, dtype=torch.int64, device=dev)
        refractory = torch.full((n,), p.refractory_steps, dtype=torch.int64, device=dev)
        refractory[torch.from_numpy(stimulus.neurons.astype(np.int64)).to(dev)] = 0
        not_silenced = torch.ones(n, dtype=torch.bool, device=dev)
        if silenced is not None and len(silenced):
            not_silenced[torch.from_numpy(np.asarray(silenced, dtype=np.int64)).to(dev)] = False
        watched = None
        if stop is not None:
            watched = torch.zeros(n, dtype=torch.bool, device=dev)
            watched[torch.from_numpy(np.asarray(stop.neurons, dtype=np.int64)).to(dev)] = True

        ring: list[torch.Tensor] = []  # indices that fired in each of the last `delay` steps
        out_i: list[torch.Tensor] = []
        out_step: list[int] = []
        steps_done, stopped = n_steps, False

        for step in range(n_steps):
            ready = (step - last) >= refractory
            v = torch.where(ready, p.v_0_mv + (v - p.v_0_mv) * self._a_v + g * self._c_g, v)
            g = torch.where(ready, g * self._a_g, g)
            fired = torch.nonzero(ready & (v > p.v_th_mv)).flatten()  # host sync; sorted ascending

            if len(ring) == delay:
                src = ring.pop(0)
                src = src[not_silenced[src]]
                if src.numel():
                    lo, hi = self._indptr[src], self._indptr[src + 1]
                    lengths = hi - lo
                    offsets = torch.cumsum(lengths, 0) - lengths
                    total = int(lengths.sum())
                    edge = torch.arange(total, device=dev) + torch.repeat_interleave(lo - offsets, lengths)
                    tgt = self._post[edge]
                    open_ = (step - last[tgt]) >= refractory[tgt]  # refractory targets drop input
                    g.index_add_(0, tgt[open_], self._w[edge][open_])
            ring.append(fired)

            if kick_ptr[step + 1] > kick_ptr[step]:
                v[kick_neuron_t[kick_ptr[step] : kick_ptr[step + 1]]] += p.poisson_kick_mv

            if fired.numel():
                v[fired] = p.v_rst_mv
                g[fired] = 0.0
                last[fired] = step
                out_i.append(fired)
                out_step.extend([step] * fired.numel())
                if watched is not None and bool(watched[fired].any()):
                    steps_done, stopped = step + 1, True
                    break

        spike_i = torch.cat(out_i).cpu().numpy().astype(np.int32) if out_i else np.empty(0, np.int32)
        self._sync()
        return TrialResult(
            spike_i=spike_i,
            spike_t_ms=np.asarray(out_step, dtype=np.float64) * p.dt_ms,
            t_sim_ms=steps_done * p.dt_ms,
            stopped_early=stopped,
            t_wall_ns=time.perf_counter_ns() - t0,
            meta={"backend": self.name, "seed": seed, "dtype": str(self.dtype)},
        )
