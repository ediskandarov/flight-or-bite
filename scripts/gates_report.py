"""Build reports/gates.md from reports/gates/G*.json (facts only)."""

from __future__ import annotations

import json
from pathlib import Path

G = {n: json.loads(Path(f"reports/gates/{n}.json").read_text()) for n in ("G1", "G2", "G3", "G4", "G5", "G6", "G7")}
TITLE = {
    "G1": "Sugar → MN9",
    "G2": "Bitter suppresses sugar",
    "G3": "Looming → DNp01",
    "G4": "Real versus shuffled",
    "G5": "Ablation",
    "G6": "Robustness",
    "G7": "Conflict versus independent race",
}
yes = lambda b: "**passed**" if b else "**FAILED**"  # noqa: E731
fmt = lambda x: "—" if x is None else (f"{x:.3g}" if isinstance(x, float) else str(x))  # noqa: E731


def mc(x: dict) -> str:
    holm = f", p(Holm) = {x['p_holm']:.2g}" if "p_holm" in x else ""
    return f"{x['control_yes']}/{x['n']} → {x['condition_yes']}/{x['n']}; b = {x['b']}, c = {x['c']}; p = {x['p']:.2g}{holm}"


L = [
    "# Validity gates (M3)",
    "",
    f"Protocol: `configs/gates.yaml`, fixed in commit `921ffaf` **before** the run; only crash testing on unrelated seeds preceded it (outputs were not inspected). Run: `{G['G1']['run_dir']}`. Connectome v783, `event` backend, frozen rate encoding (D36), D25 decoder, full 500 ms trials. Nothing was changed after viewing results. Raw results: `reports/gates/G*.json`.",
    "",
    "| # | Gate | Metric | Threshold | Status |",
    "|---|---|---|---|---|",
]
for n, r in G.items():
    L.append(f"| {n} | {TITLE[n]} | {r['metric']:.4g} | {r['threshold']:.4g} | {yes(r['passed'])} |")

d = G["G1"]["details"]
L += [
    "",
    "## G1. Sugar → MN9",
    "",
    f"Spearman ρ across all {len(d['sugar']) * d['n_rep']} trials: **{G['G1']['metric']:.3f}** (over level means: {d['rho_over_level_means']:.3f}).",
    "",
    "| sugar | " + " | ".join(f"{s:g}" for s in d["sugar"]) + " |",
    "|---|" + "---|" * len(d["sugar"]),
    "| MN9, Hz | " + " | ".join(f"{x:g}" for x in d["mn9_rate_hz_mean"]) + " |",
]
d = G["G2"]["details"]
L += [
    "",
    "## G2. Bitter suppresses sugar",
    "",
    f"sugar = 0.6, {d['n_rep']} paired trials per level. Reduction in `p_eat` from bitter 0 to bitter 1: **{G['G2']['metric']:.0%}**.",
    "",
    "| bitter | " + " | ".join(f"{b:g}" for b in d["bitter"]) + " |",
    "|---|" + "---|" * len(d["bitter"]),
    "| p_eat | " + " | ".join(f"{x:.2f}" for x in d["p_eat"]) + " |",
    "| MN9, Hz | " + " | ".join(f"{x:.1f}" for x in d["mn9_rate_hz_mean"]) + " |",
]
d = G["G3"]["details"]
L += [
    "",
    "## G3. Looming → DNp01",
    "",
    f"Spearman ρ between looming and `p_escape` across {len(d['looming'])} levels ({d['n_rep']} trials per level): **{G['G3']['metric']:.3f}**.",
    "",
    "| looming | " + " | ".join(f"{s:g}" for s in d["looming"]) + " |",
    "|---|" + "---|" * len(d["looming"]),
    "| p_escape | " + " | ".join(f"{x:.2f}" for x in d["p_escape"]) + " |",
    "| t_sim ESCAPE p50, ms | " + " | ".join(fmt(x) for x in d["t_sim_ms_p50"]) + " |",
]
d = G["G4"]["details"]
L += [
    "",
    "## G4. Real versus shuffled",
    "",
    "20 degree- and sign-preserving shuffles (seeds 1–20), identical protocol, trial seeds, and encoding (no recalibration). **Signals do not reach the output neurons in shuffled graphs:** MN9 and DNp01 do not respond, so all three metrics equal 0 on each of the 20 graphs (an undefined metric for a constant response is treated as 0).",
    "",
    "| Metric | Real graph | Null 95th percentile | Null maximum | Null values > 0 | Outside null distribution |",
    "|---|---|---|---|---|---|",
]
for g in ("G1", "G2", "G3"):
    x = d[g]
    L.append(
        f"| {g} | {x['real']:.3f} | {x['null_percentile']:.3f} | {x['null_max']:.3f} | {sum(v > 0 for v in x['null'])} of {len(x['null'])} | {'yes' if x['outside'] else 'no'} |"
    )
d = G["G5"]["details"]
L += [
    "",
    "## G5. Ablation",
    "",
    "An ablated neuron cannot spike.",
    "",
    f"- Both DNp01 neurons ablated, looming = 1.0: `p_escape` = **{d['dnp01_ablated']['p_escape']:.2f}** (intact {d['dnp01_ablated']['p_escape_intact']:.2f}; criterion ≤ {d['dnp01_ablated']['max']}) — {'met' if d['criteria']['dnp01'] else 'NOT met'}.",
    f"- MN9 ablated, sugar = 1.0: `p_eat` = **{d['mn9_ablated']['p_eat']:.2f}** (intact {d['mn9_ablated']['p_eat_intact']:.2f}; criterion ≤ {d['mn9_ablated']['max']}) — {'met' if d['criteria']['mn9'] else 'NOT met'}.",
    f"- M_loom (25 neurons): retained effect fraction **{d['m_loom_ablated']['retained']:.2f}** (criterion ≤ {d['m_loom_ablated']['max_retained']}) — {'met' if d['criteria']['m_loom'] else 'NOT met'}.",
    f"- cL20 alone: retained effect fraction **{d['cl20_ablated']['retained']:.2f}** (no criterion). **Ablating cL20 does not remove the effect.** Its targets on this path are LC4 (343 synapses) and LPLC2 (2), out of 361 synapses onto looming-active DNp01 partners; these are clamped sources in the model (each Poisson input forces a spike regardless of inhibition), so this pathway is invisible by construction. Separate verification (`runs/cl20_check.json`): 17,916 LPLC2/LC4 spikes in 60 paired trials, zero differing sugar/no-sugar pairs. The model mechanism is carried by the other 24 M_loom neurons: ablating them while retaining cL20 removes the effect (b − c: 34 → 0, identical seeds).",
    "",
    "Effect = b − c pooled over three looming levels (outcome: DNp01 spiked, looming-only versus sugar 0.6 + looming, identical seeds; ablation in both arms). Format: control → condition.",
    "",
    "| Condition | looming 0.6 | looming 0.8 | looming 1.0 | Pooled | b − c |",
    "|---|---|---|---|---|---|",
]
for label, key in (
    ("intact", "suppression_intact"),
    ("M_loom ablated", "m_loom_ablated"),
    ("cL20 ablated", "cl20_ablated"),
):
    x = d[key]
    L.append(
        f"| {label} | "
        + " | ".join(mc(x["levels"][lv]) for lv in ("0.6", "0.8", "1.0"))
        + f" | {mc(x['pooled'])} | {x['effect_b_minus_c']} |"
    )
d = G["G6"]["details"]
L += [
    "",
    "## G6. Robustness",
    "",
    "**Failed.** Under SPEC §5 the final report must explicitly state: **“conclusions depend on manually chosen parameters.”** Both failed variants are ×0.5 weakening (`r_max_sugar × 0.5` and `w_syn × 0.5`); the network is silent (signals do not reach readout neurons), with no sign reversal.",
    "",
    f"A variant passes if affected gates retain direction and monotonicity: G1 ρ > 0.8, G3 ρ > 0.8, G2 reduction > 0. Passed: **{int(G['G6']['metric'])} of {int(G['G6']['threshold'])}**. Fewer repetitions than in the main gates (G1 10, G2 20, G3 20); seeds offset by 100,000.",
    "",
    "| Variant | G1: ρ | G2: p_eat reduction (p_eat at bitter 0 → 1) | G3: ρ | Passes |",
    "|---|---|---|---|---|",
]
for v in d["variants"]:
    g2 = "—" if "G2" not in v else f"{v['G2']['metric']:.2f} ({v['G2']['p_eat'][0]:.2f} → {v['G2']['p_eat'][-1]:.2f})"
    L.append(
        f"| `{v['variant']}` | {fmt(v.get('G1', {}).get('metric'))} | {g2} | {fmt(v.get('G3', {}).get('metric'))} | {'yes' if v['passed'] else '**no**'} |"
    )
failed = [v for v in d["variants"] if not v["passed"]]
for v in failed:
    L += ["", f"Details for `{v['variant']}`:"]
    if "G1" in v:
        L.append("- MN9, Hz by sugar level: " + " / ".join(f"{x:g}" for x in v["G1"]["mn9_rate_hz_mean"]))
    if "G3" in v:
        L.append("- p_escape by looming level: " + " / ".join(f"{x:.2f}" for x in v["G3"]["p_escape"]))
d = G["G7"]["details"]
L += [
    "",
    "## G7. Conflict versus independent race (RQ1)",
    "",
    "Null model: circuits are independent, so sugar input cannot change whether DNp01 spikes. sugar = 0.6, looming-only control on identical seeds, 40 pairs per level, exact two-sided McNemar test, Holm correction across three levels.",
    "",
    "| looming | DNp01 spiked: control → condition; b, c; p | Control decisions EAT / ESCAPE / IDLE | Condition decisions |",
    "|---|---|---|---|",
]
for lv, x in d["levels"].items():
    a, b = x["decisions_control"], x["decisions_condition"]
    L.append(
        f"| {lv} | {mc(x)} | {a['EAT']} / {a['ESCAPE']} / {a['IDLE']} | {b['EAT']} / {b['ESCAPE']} / {b['IDLE']} |"
    )
L += [
    f"| pooled | {mc(d['pooled'])} | | |",
    "",
    f"Minimum Holm-adjusted p: **{G['G7']['metric']:.2g}** (threshold {G['G7']['threshold']}).",
]
L += [
    "",
    "## Consequences under SPEC §5",
    "",
    "- Failure of G1–G3 or G5 → stop and ask the human author. Failure of G4 → publish the negative result. Failure of G6 → state “conclusions depend on manually chosen parameters.” Failure of G7 → label “connectome = race of reflexes.”",
    "- Not done in M3: G1 on Brian2 with frozen encoding (reference checked in M1 at `R_max` = 200 Hz: `reports/gates/G1_m1_r200.json`); recalibration on shuffled graphs.",
    "",
]
Path("reports/gates.md").write_text("\n".join(L))
print("wrote reports/gates.md")
