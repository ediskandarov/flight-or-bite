"""ConnectomeArbiter (SPEC §4.1): one LIF simulation of the connectome per decision, online.

The graph is loaded once; every decision is one trial with early stopping at the decoder's event.
The action is native (decision D27): the outcome of that single simulation.
"""

from __future__ import annotations

import time

import numpy as np

from flight_or_bite.arbiters.baselines import one_hot
from flight_or_bite.lif.graph import Connectome
from flight_or_bite.lif.trial import TrialRunner, load_real_connectome
from flight_or_bite.types import Decision, Observation


class ConnectomeArbiter:
    def __init__(self, connectome: Connectome | None = None, *, name: str = "connectome",
                 runner: TrialRunner | None = None) -> None:  # fmt: skip
        t0 = time.perf_counter()
        self.name = name
        self.runner = runner or TrialRunner(connectome or load_real_connectome())
        self.t_load_s = time.perf_counter() - t0  # reported separately from decisions (SPEC §6.2)

    def decide(self, obs: Observation, rng: np.random.Generator) -> Decision:
        t0 = time.perf_counter_ns()  # t_wall covers input generation and the simulation
        seed = int(rng.integers(2**31 - 1))
        trial = self.runner.run(obs, seed, early_stop=True)
        d = trial.decoded
        return Decision(
            probs=one_hot(d.action), action=d.action, t_wall_ns=time.perf_counter_ns() - t0,
            t_sim_ms=d.t_sim_ms,
            meta={"trial_seed": seed, "n_spikes": trial.n_spikes, "n_active": trial.n_active,
                  "tie": d.tie, "backend": "event"},
        )  # fmt: skip
