"""Event-driven LIF on NumPy/Numba (SPEC §4.1, candidate 2).

Only neurons that activity has reached are updated: a neuron at exact rest (v = v_0, g = 0) is a
fixed point of the update, so skipping it changes nothing (in a sugar trial ~9% of the network
is ever touched). Spikes propagate only along the outgoing edges of neurons that fired.
Within a step the order of operations is Brian2's schedule for this model:

    1. state update   exact solution of the linear ODE, skipped while refractory
    2. threshold      v > v_th and not refractory
    3. synapses       deliver spikes emitted `delay_steps` ago (g += w); Poisson kicks (v += k)
    4. reset          v = v_rst, g = 0 for neurons that fired in step 2

Input arriving in the step a neuron fires is wiped by its reset. Input arriving while the target
is refractory is dropped: Brian2 gates `g += w` by `not_refractory` because `g` carries the
"(unless refractory)" flag (verified on a toy chain against Brian2 2.10.1 state traces).
The kernel is deterministic: Poisson kicks come in as a precomputed
schedule, which also allows replaying the input spikes of a Brian2 run (see `replay_schedule`).
"""

from __future__ import annotations

import math
import time

import numpy as np
from numba import njit

from flight_or_bite.lif.backend import Stimulus, StopOnFirstSpike, TrialResult
from flight_or_bite.lif.graph import Connectome
from flight_or_bite.lif.params import LIFParams

NEVER = -(2**40)


@njit(cache=True)
def _simulate(
    indptr, post, count, w_syn, silenced, ablated,
    kick_ptr, kick_neuron, kick_mv,
    refractory_steps, watched, burst_neuron, burst_k, burst_window_steps,
    n_steps, delay, v_0, v_rst, v_th, a_v, a_g, c_g,
):  # fmt: skip
    n = indptr.shape[0] - 1
    v = np.full(n, v_0)
    g = np.zeros(n)
    last = np.full(n, NEVER, dtype=np.int64)
    active = np.empty(n, dtype=np.int32)  # neurons that have left exact rest, in arrival order
    is_active = np.zeros(n, dtype=np.bool_)
    n_active = 0

    ring = np.empty((delay + 1, n), dtype=np.int32)  # spikes emitted in each of the last steps
    ring_n = np.zeros(delay + 1, dtype=np.int64)

    cap = 1 << 16
    out_i = np.empty(cap, dtype=np.int32)
    out_step = np.empty(cap, dtype=np.int64)
    n_out = 0
    steps_done = n_steps
    stopped = False
    burst_ring = np.full(max(burst_k, 1), NEVER, dtype=np.int64)  # last burst_k spike steps
    burst_n = 0

    for step in range(n_steps):
        slot = step % (delay + 1)
        fired = ring[slot]
        n_fired = 0

        # 1 + 2: state update, then threshold
        for a in range(n_active):
            i = active[a]
            if step - last[i] >= refractory_steps[i]:
                dv = v[i] - v_0
                v[i] = v_0 + dv * a_v + g[i] * c_g
                g[i] *= a_g
                if v[i] > v_th and not ablated[i]:
                    fired[n_fired] = i
                    n_fired += 1
        ring_n[slot] = n_fired
        # Deliver in neuron-index order, as Brian2 does: keeps the float sums in g bit-identical.
        for a in range(1, n_fired):
            x = fired[a]
            b = a - 1
            while b >= 0 and fired[b] > x:
                fired[b + 1] = fired[b]
                b -= 1
            fired[b + 1] = x

        # 3: deliver spikes emitted `delay` steps ago, then Poisson kicks
        if step >= delay:
            src_slot = (step - delay) % (delay + 1)
            src = ring[src_slot]
            for k in range(ring_n[src_slot]):
                j = src[k]
                if not silenced[j]:
                    for e in range(indptr[j], indptr[j + 1]):
                        t = post[e]
                        if step - last[t] >= refractory_steps[t]:  # refractory targets drop input
                            g[t] += count[e] * w_syn
                            if not is_active[t]:
                                is_active[t] = True
                                active[n_active] = t
                                n_active += 1
        for k in range(kick_ptr[step], kick_ptr[step + 1]):
            t = kick_neuron[k]
            v[t] += kick_mv
            if not is_active[t]:
                is_active[t] = True
                active[n_active] = t
                n_active += 1

        # 4: reset, record, stop check
        hit = False
        for k in range(n_fired):
            i = fired[k]
            v[i] = v_rst
            g[i] = 0.0
            last[i] = step
            if watched[i]:
                hit = True
            if i == burst_neuron:  # burst criterion: burst_k spikes less than the window apart
                burst_ring[burst_n % burst_k] = step
                burst_n += 1
                if burst_n >= burst_k and step - burst_ring[burst_n % burst_k] < burst_window_steps:
                    hit = True
            if n_out == cap:
                cap *= 2
                grown_i = np.empty(cap, dtype=np.int32)
                grown_step = np.empty(cap, dtype=np.int64)
                grown_i[:n_out] = out_i[:n_out]
                grown_step[:n_out] = out_step[:n_out]
                out_i = grown_i
                out_step = grown_step
            out_i[n_out] = i
            out_step[n_out] = step
            n_out += 1
        if hit:
            steps_done = step + 1
            stopped = True
            break

    return out_i[:n_out], out_step[:n_out], steps_done, stopped, n_active


def poisson_schedule(
    stimulus: Stimulus, n_steps: int, dt_ms: float, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Bernoulli(rate * dt) per neuron and step, as Brian2's PoissonInput with N=1."""
    p = stimulus.rates_hz * dt_ms * 1e-3
    if np.any(p > 1) or np.any(p < 0):
        raise ValueError("Poisson rate outside [0, 1/dt]")
    steps, cols = np.nonzero(rng.random((n_steps, len(p))) < p)
    return steps.astype(np.int64), stimulus.neurons[cols].astype(np.int32)


def replay_schedule(
    spike_i: np.ndarray, spike_t_ms: np.ndarray, neurons: np.ndarray, dt_ms: float
) -> tuple[np.ndarray, np.ndarray]:
    """Kick schedule reproducing recorded spikes of stimulated neurons.

    A kick in step s makes the (non-refractory) target fire in step s + 1 and the reset then
    clears it, so spikes and effective kicks correspond one to one.
    """
    keep = np.isin(spike_i, neurons)
    steps = np.rint(spike_t_ms[keep] / dt_ms).astype(np.int64) - 1
    if np.any(steps < 0):
        raise ValueError("a stimulated neuron fired in step 0, before any kick could land")
    order = np.argsort(steps, kind="stable")
    return steps[order], spike_i[keep][order].astype(np.int32)


class EventBackend:
    name = "event-numba"

    def __init__(self, connectome: Connectome, params: LIFParams) -> None:
        t0 = time.perf_counter()
        self.connectome = connectome
        self.params = params
        p = params
        self._a_v = math.exp(-p.dt_ms / p.t_mbr_ms)
        self._a_g = math.exp(-p.dt_ms / p.tau_ms)
        self._c_g = p.tau_ms / (p.tau_ms - p.t_mbr_ms) * (self._a_g - self._a_v)
        self.run_trial(Stimulus.uniform(np.array([0]), 0.0), p.dt_ms * 2, seed=0)  # JIT warm-up
        self.t_load_s = time.perf_counter() - t0

    def run_trial(
        self,
        stimulus: Stimulus,
        t_max_ms: float,
        seed: int,
        stop: StopOnFirstSpike | None = None,
        silenced: np.ndarray | None = None,
        kicks: tuple[np.ndarray, np.ndarray] | None = None,
        ablated: np.ndarray | None = None,
        stop_on_burst: tuple[int, int, int] | None = None,
    ) -> TrialResult:
        """`kicks` = (steps, neurons) replaces the random Poisson schedule (replay mode).

        `stop_on_burst` = (neuron, k, window_steps): also stop when `neuron` has fired k spikes
        fewer than window_steps apart — the decoder's EAT criterion, for online use.

        `silenced` neurons keep firing but have no effect on others (model.py's `silence`);
        `ablated` neurons cannot fire at all — needed when the neuron itself is the read-out.
        """
        t0 = time.perf_counter_ns()
        p, con = self.params, self.connectome
        n_steps = round(t_max_ms / p.dt_ms)

        if kicks is None:
            kicks = poisson_schedule(stimulus, n_steps, p.dt_ms, np.random.default_rng(seed))
        kick_step, kick_neuron = kicks
        in_window = kick_step < n_steps
        kick_step, kick_neuron = kick_step[in_window], kick_neuron[in_window]
        kick_ptr = np.zeros(n_steps + 1, dtype=np.int64)
        np.cumsum(np.bincount(kick_step, minlength=n_steps), out=kick_ptr[1:])

        refractory_steps = np.full(con.n_neurons, p.refractory_steps, dtype=np.int64)
        refractory_steps[stimulus.neurons] = 0  # no refractory period for Poisson targets
        silenced_mask = np.zeros(con.n_neurons, dtype=np.bool_)
        if silenced is not None:
            silenced_mask[silenced] = True
        ablated_mask = np.zeros(con.n_neurons, dtype=np.bool_)
        if ablated is not None:
            ablated_mask[ablated] = True
        burst_neuron, burst_k, burst_window_steps = stop_on_burst or (-1, 1, 0)
        watched = np.zeros(con.n_neurons, dtype=np.bool_)
        if stop is not None:
            watched[stop.neurons] = True

        spike_i, spike_step, steps_done, stopped, n_active = _simulate(
            con.indptr, con.post, con.count, p.w_syn_mv, silenced_mask, ablated_mask,
            kick_ptr, kick_neuron, p.poisson_kick_mv,
            refractory_steps, watched, burst_neuron, burst_k, burst_window_steps,
            n_steps, p.delay_steps, p.v_0_mv, p.v_rst_mv, p.v_th_mv,
            self._a_v, self._a_g, self._c_g,
        )  # fmt: skip
        return TrialResult(
            spike_i=spike_i,
            spike_t_ms=spike_step * p.dt_ms,
            t_sim_ms=steps_done * p.dt_ms,
            stopped_early=bool(stopped),
            t_wall_ns=time.perf_counter_ns() - t0,
            meta={"backend": self.name, "seed": seed, "n_active": int(n_active)},
        )
