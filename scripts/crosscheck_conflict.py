"""Spike-for-spike check of the event backend against Brian2 on conflict trials.

10 trials, sugar 0.6 + looming 0.8, hunger 0, frozen encoding. Brian2 is the reference and draws
the input itself (one PoissonInput per stimulated neuron, as in model.py); the spikes of the
stimulated neurons are then replayed into the event backend, so both simulators see identical
input. Every spike of the whole network is compared as a (neuron, 0.1 ms step) pair, and the
decoder is applied to both.
"""

from __future__ import annotations

import json

import numpy as np

from flight_or_bite.lif.backend import Stimulus
from flight_or_bite.lif.brian2_backend import Brian2Backend
from flight_or_bite.lif.decoder import decode
from flight_or_bite.lif.event_backend import replay_schedule
from flight_or_bite.lif.perf import spike_pairs
from flight_or_bite.lif.trial import TrialRunner, load_real_connectome
from flight_or_bite.runlog import start_run
from flight_or_bite.types import Observation

OBS = Observation(sugar=0.6, bitter=0.0, looming=0.8, hunger=0.0)
SEEDS = range(10)

con = load_real_connectome()
runner = TrialRunner(con)  # event backend + frozen encoding + neuron sets
enc, params = runner.enc, runner.params
rates = enc.rates(OBS)
neurons = np.concatenate([runner.sets["sugar"], runner.sets["looming"]]).astype(np.int32)
hz = np.concatenate(
    [
        np.full(len(runner.sets["sugar"]), rates["sugar"]),
        np.full(len(runner.sets["looming"]), rates["looming"]),
    ]
)
stim = Stimulus(neurons, hz)
run_dir = start_run(
    "crosscheck-conflict",
    {"obs": OBS.__dict__, "rates_hz": rates, "n_stimulated": len(neurons), "seeds": list(SEEDS)},
)
reference = Brian2Backend(con, params)
rows = []
for seed in SEEDS:
    a = reference.run_trial(stim, enc.t_sim_ms, seed=seed)
    kicks = replay_schedule(a.spike_i, a.spike_t_ms, neurons, params.dt_ms)
    b = runner.backend.run_trial(stim, enc.t_sim_ms, seed=seed, kicks=kicks)
    pa, pb = spike_pairs(a, params.dt_ms), spike_pairs(b, params.dt_ms)
    da, db = (
        decode(
            r,
            runner.mn9,
            runner.dnp01,
            theta_eat_hz=enc.theta_eat_hz,
            eat_window_ms=enc.eat_window_ms,
            t_sim_ms=enc.t_sim_ms,
        )
        for r in (a, b)
    )
    rows.append({"seed": seed, "brian2_spikes": len(pa), "event_spikes": len(pb), "identical": len(pa & pb), "only_brian2": len(pa - pb),
                 "only_event": len(pb - pa), "input_spikes": int(np.isin(a.spike_i, neurons).sum()), "active_neurons": int(np.unique(a.spike_i).size),
                 "brian2_action": da.action.value, "event_action": db.action.value, "brian2_t_sim_ms": da.t_sim_ms, "event_t_sim_ms": db.t_sim_ms,
                 "mn9_spikes": int((a.spike_i == runner.mn9).sum()), "dnp01_spikes": int(np.isin(a.spike_i, runner.dnp01).sum()),
                 "brian2_wall_s": a.t_wall_ns / 1e9, "event_wall_s": b.t_wall_ns / 1e9})  # fmt: skip
    print(rows[-1], flush=True)
(run_dir / "crosscheck.json").write_text(json.dumps({"rows": rows, "run_dir": str(run_dir)}, indent=2))
print("DONE", run_dir, flush=True)
