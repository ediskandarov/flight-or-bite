"""Reference backend: the Shiu et al. model on Brian2, mirroring model.py (SPEC §4.1).

Differences from model.py, none of which touch the dynamics: the network is built once and
restored between trials instead of rebuilt; trials can stop early; spikes come back as arrays.
"""

from __future__ import annotations

import subprocess
import sys
import time
from textwrap import dedent

import numpy as np

from flight_or_bite.lif.backend import Stimulus, StopOnFirstSpike, TrialResult
from flight_or_bite.lif.graph import Connectome
from flight_or_bite.lif.params import LIFParams

# Verbatim from model.py. `w = 0` in the reset is a no-op there too (an unused temporary).
EQS = dedent("""
    dv/dt = (v_0 - v + g) / t_mbr : volt (unless refractory)
    dg/dt = -g / tau               : volt (unless refractory)
    rfc                            : second
    """)
EQ_TH = "v > v_th"
EQ_RST = "v = v_rst; w = 0; g = 0 * mV"


def _macos_sdk_link_args() -> list[str]:
    """Point the linker at an SDK that exists.

    The interpreter records the SDK it was built against (here Homebrew Python 3.12 and
    MacOSX14.sdk); when that SDK is absent the link step fails with "library 'c++' not found".
    The last -isysroot wins.
    """
    if sys.platform != "darwin":
        return []
    try:
        sdk = subprocess.run(
            ["xcrun", "--show-sdk-path"], capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return []
    return ["-isysroot", sdk] if sdk else []


class Brian2Backend:
    name = "brian2"
    _instances = 0  # Brian2 object names must be unique within a process

    def __init__(
        self,
        connectome: Connectome,
        params: LIFParams,
        *,
        codegen_target: str = "cython",
        stop_check_ms: float = 1.0,
    ) -> None:
        import brian2 as b2

        t0 = time.perf_counter()
        Brian2Backend._instances += 1
        tag = self._tag = Brian2Backend._instances
        self._poisson_pool: dict[tuple[int, float], object] = {}
        self._b2 = b2
        self.params = params
        self.stop_check_ms = stop_check_ms
        self.name = f"brian2-{codegen_target}"
        b2.prefs.codegen.target = codegen_target
        if codegen_target == "cython":
            b2.prefs.codegen.cpp.extra_link_args = _macos_sdk_link_args()
        b2.defaultclock.dt = params.dt_ms * b2.ms

        self._namespace = {
            "v_0": params.v_0_mv * b2.mV,
            "v_rst": params.v_rst_mv * b2.mV,
            "v_th": params.v_th_mv * b2.mV,
            "t_mbr": params.t_mbr_ms * b2.ms,
            "tau": params.tau_ms * b2.ms,
        }
        self.neu = b2.NeuronGroup(
            N=connectome.n_neurons,
            model=EQS,
            method="linear",
            threshold=EQ_TH,
            reset=EQ_RST,
            refractory="rfc",
            name=f"default_neurons_{tag}",
            namespace=self._namespace,
        )
        self.neu.v = params.v_0_mv * b2.mV
        self.neu.g = 0
        self.neu.rfc = params.t_rfc_ms * b2.ms

        self.syn = b2.Synapses(
            self.neu,
            self.neu,
            "w : volt",
            on_pre="g += w",
            delay=params.t_dly_ms * b2.ms,
            name=f"default_synapses_{tag}",
        )
        self.syn.connect(i=connectome.pre(), j=connectome.post)
        self._w_volt = connectome.count * (params.w_syn_mv * 1e-3)
        self._syn_pre = connectome.pre()
        self.syn.w = self._w_volt * b2.volt

        self.mon = b2.SpikeMonitor(self.neu)
        self.net = b2.Network(self.neu, self.syn, self.mon)
        self.net.store("rest")
        self.t_load_s = time.perf_counter() - t0

    def _poisson_input(self, idx: int, rate_hz: float):
        """One PoissonInput per (neuron, rate), as in model.py, but created once and reused.

        Brian2 compiles a Cython module for every new object (~4 s each here), and an object that
        has been simulated cannot be re-added to a network. Inputs therefore stay in the network
        for good and are switched with their `active` flag.
        """
        b2 = self._b2
        key = (idx, rate_hz)
        if key not in self._poisson_pool:
            self._poisson_pool[key] = b2.PoissonInput(
                target=self.neu[idx : idx + 1],
                target_var="v",
                N=1,
                rate=rate_hz * b2.Hz,
                weight=self.params.poisson_kick_mv * b2.mV,
            )
            self.net.add(self._poisson_pool[key])
        return self._poisson_pool[key]

    def run_trial(
        self,
        stimulus: Stimulus,
        t_max_ms: float,
        seed: int,
        stop: StopOnFirstSpike | None = None,
        silenced: np.ndarray | None = None,
    ) -> TrialResult:
        b2 = self._b2
        t0 = time.perf_counter_ns()
        self.net.restore("rest")
        b2.seed(seed)

        for source in self._poisson_pool.values():
            source.active = False
        for idx, rate in zip(stimulus.neurons.tolist(), stimulus.rates_hz.tolist(), strict=True):
            if rate > 0:
                self._poisson_input(idx, rate).active = True
        extras: list = []
        if len(stimulus.neurons):
            self.neu.rfc[stimulus.neurons] = 0 * b2.ms  # no refractory period for Poisson targets

        if silenced is not None and len(silenced):  # model.py `silence`: zero outgoing weights
            w = self._w_volt.copy()
            w[np.isin(self._syn_pre, silenced)] = 0.0
            self.syn.w = w * b2.volt

        stopped = {"early": False}
        if stop is not None:
            watched = np.asarray(stop.neurons)

            @b2.network_operation(dt=self.stop_check_ms * b2.ms, when="end")
            def check_stop() -> None:
                if self.mon.count[watched].sum() > 0:
                    stopped["early"] = True
                    self.net.stop()

            extras.append(check_stop)

        self.net.add(*extras)
        try:
            self.net.run(t_max_ms * b2.ms, namespace=self._namespace)
            t_sim_ms = float(self.net.t / b2.ms)
            spike_i = np.asarray(self.mon.i, dtype=np.int32).copy()
            spike_t_ms = np.asarray(self.mon.t / b2.ms, dtype=np.float64).copy()
        finally:
            self.net.remove(*extras)

        return TrialResult(
            spike_i=spike_i,
            spike_t_ms=spike_t_ms,
            t_sim_ms=t_sim_ms,
            stopped_early=stopped["early"],
            t_wall_ns=time.perf_counter_ns() - t0,
            meta={"backend": self.name, "seed": seed},
        )
