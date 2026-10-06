"""`fob report`: reports/final_report.md and PNG figures, from artefacts only (SPEC §10).

The text states what PREREG.md asks to be stated and nothing more; a missing artefact is printed as
missing, never filled in. Wording: “LIF simulation of the connectome,” “arbiter,” “policy” (SPEC §14).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from flight_or_bite.report import analyses, figures

OUT = Path("reports/final_report.md")
MISSING = "_No data: artifact not yet available._"
G6_SENTENCE = "conclusions depend on manually chosen parameters"
EXPLORATORY = ["probe_looming.md", "probe_jev.md", "probe_interaction.md", "probe_r5.md", "grid_loss.md",
               "env_sweep.md", "calibration.md", "jev_mode_selection.md", "eval_dev.md", "perf.md"]  # fmt: skip


def _ci(v: list[float] | None, fmt: str = "+.1f") -> str:
    return "—" if not v else f"[{v[0]:{fmt}}, {v[1]:{fmt}}]"


def _p(p: float | None) -> str:
    return "—" if p is None else (f"{p:.2g}" if p < 0.001 else f"{p:.4f}")


def _yes(flag: bool) -> str:
    return "**confirmed**" if flag else "**not confirmed**"


def _fig(path: str | None, caption: str) -> list[str]:
    return ["", f"![{caption}]({path})", f"*{caption}*", ""] if path else []


def main_metric(s: dict | None, title: str, primary: bool) -> list[str]:
    out = [f"## {title}", ""]
    if not s:
        return out + [MISSING, ""]
    retry_count = sum(s["retried_decisions"].values())
    out += [f"Paired episodes: **{s['episodes']}**; stops under the Jev failure policy (PREREG §2b): **{len(s['stops'])}**; "
            f"decisions retried after a network error: {retry_count}.", "",
            "| Arbiter | Lifetime, trials: mean [95% CI] | Median | % of oracle [95% CI] | Deaths: predator / starvation / "
            "toxin / survived | EAT / ESCAPE / IDLE | Mean energy | Final energy |", "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for n, r in s["arbiters"].items():
        c, a = r["causes"], r["actions"]
        alive = c["censored"]
        out.append(f"| `{n}` | {r['lifetime_mean']:.1f} {_ci(r['lifetime_ci95'], '.1f')} | {r['lifetime_median']:.0f} | "
                   f"{r['percent_of_oracle']:.1%} {_ci([100 * x for x in r['percent_of_oracle_ci95']], '.0f')} | "
                   f"{c['predator']:.0%} / {c['starvation']:.0%} / {c['toxin']:.0%} / {alive:.0%} | "
                   f"{a['eat']:.0%} / {a['escape']:.0%} / {a['idle']:.0%} | {r['mean_energy']:.1f} | "
                   f"{r['final_energy_mean']:.1f} |")  # fmt: skip
    pairs = s["paired_differences"]
    key = next((k for k in pairs if set(k.split(" - ")) == set(analyses.MAIN)), None)
    if key:
        d = pairs[key]
        verdict = ("CI excludes zero — winner under PREREG §2: `"
                   + (key.split(" - ")[0] if d["mean_diff"] > 0 else key.split(" - ")[1]) + "`"
                   if d["significant"] else "CI includes zero — no winner declared under PREREG §2")  # fmt: skip
        label = "Primary comparison (the only one used to declare a winner)" if primary else "Comparison"
        if not primary:
            verdict = ("CI excludes zero" if d["significant"] else "CI includes zero")
            verdict += "; this is a secondary analysis and does not determine the primary-comparison winner"
        out += ["", f"**{label}: {key} = {d['mean_diff']:+.1f} trials, 95% CI {_ci(d['ci95'])}.** {verdict}."]
    out += ["", "Other paired differences (descriptive):", "", "| Comparison | Difference | 95% CI | CI excludes zero |",
            "|---|---|---|---|"]  # fmt: skip
    out += [f"| {k} | {d['mean_diff']:+.1f} | {_ci(d['ci95'])} | {'yes' if d['significant'] else 'no'} |"
            for k, d in pairs.items() if k != key]  # fmt: skip
    for stop in s["stops"]:
        out.append(f"- stop {stop['ts']}: `{stop['arbiter']}`, seed {stop['seed']}: {stop['error'][:160]}")
    return out + [""]


def mcnemar_table(h: dict, outcome: str) -> list[str]:
    out = [
        f"| looming | Pairs | “{outcome}”: control | Condition | b | c | p | p (Holm) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    out += [f"| {lv} | {x['n']} | {x['control_yes']} | {x['condition_yes']} | {x['b']} | {x['c']} | {_p(x['p'])} | "
            f"{_p(x['p_holm'])} |" for lv, x in h["levels"].items()]  # fmt: skip
    return out


def hypotheses(c: dict | None, h5: dict | None) -> list[str]:
    out = ["## 3. Confirmatory LIF connectome hypotheses (RQ1; PREREG §3)", ""]
    if not c:
        return out + [MISSING, ""]
    out += [f"Computed once on PREREG seeds; {c['n_pairs']} pairs per looming level; Holm correction across three "
            f"levels within each hypothesis; α = 0.05. Run: `{c.get('run_dir', '?')}`.", ""]  # fmt: skip
    h = c["H1"]
    out += [f"### H1. Sugar 0.6 reduces the probability of a DNp01 spike — {_yes(h['confirmed'])}", "",
            f"Minimum Holm-adjusted p: {_p(h['min_p_holm'])}; b > c at all levels with discordant pairs: "
            f"{'yes' if h['b_gt_c_wherever_discordant'] else 'no'}.", "", *mcnemar_table(h, "DNp01 spiked"), ""]  # fmt: skip
    h = c["H2"]
    doses = list(next(iter(h["levels"].values()))["spiked_by_dose"])
    out += [f"### H2. Suppression increases monotonically with sugar dose — {_yes(h['confirmed'])}", "",
            f"One-sided permutation trend test; minimum p (Holm): {_p(h['min_p_holm'])}.", "",
            "| looming | " + " | ".join(f"DNp01 spikes at sugar {d}" for d in doses) + " | Out of | p | p (Holm) |",
            "|---|" + "---|" * (len(doses) + 3)]  # fmt: skip
    out += [f"| {lv} | " + " | ".join(str(x["spiked_by_dose"][d]) for d in doses) +
            f" | {x['n']} | {_p(x['p'])} | {_p(x['p_holm'])} |" for lv, x in h["levels"].items()]  # fmt: skip
    h = c["H3"]
    out += ["", f"### H3. M_loom ablation removes the effect — {_yes(h['confirmed'])}", "",
            f"Sign test on nonzero d; minimum p (Holm): {_p(h['min_p_holm'])}. Effect fraction retained after "
            f"ablation (pooled over levels): {h['retained_fraction'] if h['retained_fraction'] is None else round(h['retained_fraction'], 3)}"
            f", 95% CI {_ci(h['retained_ci95'], '.3f')}.", "",
            "| looming | Intact effect (control − condition) | Ablated effect | d > 0 | d < 0 | Σd | p | p (Holm) |",
            "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    out += [f"| {lv} | {x['effect_intact']} | {x['effect_ablated']} | {x['d_positive']} | {x['d_negative']} | {x['sum_d']} | "
            f"{_p(x['p'])} | {_p(x['p_holm'])} |" for lv, x in h["levels"].items()]  # fmt: skip
    h = c["H4"]
    add = h["additional_outcome_dnp01_spiked"]
    out += ["", f"### H4. Hunger 1 versus 0 at sugar 0.6 reduces P(ESCAPE) — {_yes(h['confirmed'])}", "",
            f"Primary outcome: decoder chose ESCAPE; minimum p (Holm): {_p(h['min_p_holm'])}.", "",
            *mcnemar_table(h, "ESCAPE"), "",
            f"Additional outcome “DNp01 spiked” (excluded from the criterion): minimum p (Holm) {_p(add['min_p_holm'])}; "
            f"would meet the same criterion: {'yes' if add['confirmed'] else 'no'}.", "", *mcnemar_table(add, "DNp01 spiked"), ""]  # fmt: skip
    out += ["## 4. Planned H1 robustness analysis (PREREG §4; not confirmatory)", "",
            "| No. | Variant | Outcome | Control / condition yes counts (out of 100), by looming level | b / c by looming level | Direction retained (b > c) | Minimum p (Holm) | Significant |",
            "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in sorted(c["robustness"], key=lambda r: r["variant"]):
        bc = "; ".join(f"{lv}: {x['b']} / {x['c']}" for lv, x in r["levels"].items())
        yes = "; ".join(f"{lv}: {x['control_yes']} / {x['condition_yes']}" for lv, x in r["levels"].items())
        out.append(f"| {r['variant']} | {r['name']} | {r['outcome']} | {yes} | {bc} | "
                   f"{'yes' if r['b_gt_c_wherever_discordant'] else 'no'} | {_p(r['min_p_holm'])} | "
                   f"{'yes' if r['min_p_holm'] < 0.05 else 'no'} |")  # fmt: skip
    out += ["", "The ×0.5 weakening variants (`r_max_sugar × 0.5`, `w_syn × 0.5`) are excluded: **“the network is silent”** "
            "(PREREG §4).", ""]  # fmt: skip
    out += ["## 5. H5: sugar shifts Jev's escape curve (RQ3; PREREG §5)", ""]
    if not h5:
        return out + [MISSING, ""]
    out += [f"Confirmatory claim Δ_Jev ≠ 0 — {_yes(h5['confirmed'])}. Mode `{h5['jev_mode']}`, model "
            f"{', '.join(h5['jev_models'])}; retried calls: {h5['jev_retried_calls']}.", "",
            "| Arbiter | Δ (mean across 11 looming levels) | 95% CI | Sign | Δ − Δ_oracle | 95% CI |", "|---|---|---|---|---|---|",
            f"| oracle | {h5['delta_oracle']:+.4f} | — | {'−' if h5['delta_oracle'] < 0 else '+'} | — | — |"]  # fmt: skip
    for n in ("jev", "connectome"):
        d = h5[f"delta_{n}"]
        out.append(f"| {n} | {d:+.4f} | {_ci(h5[f'delta_{n}_ci95'], '+.4f')} | {'−' if d < 0 else '+' if d > 0 else '0'} | "
                   f"{h5[f'delta_{n}_minus_oracle']:+.4f} | {_ci(h5[f'delta_{n}_minus_oracle_ci95'], '+.4f')} |")  # fmt: skip
    out += ["", "`p_escape` by looming level (bitter 0, hunger 0.5):", "",
            "| Arbiter, sugar | " + " | ".join(f"{x:.1f}" for x in h5["looming"]) + " |", "|---|" + "---|" * len(h5["looming"])]  # fmt: skip
    for n in ("oracle", "jev", "connectome"):
        out += [f"| {n}, {s} | " + " | ".join(f"{v:.2f}" for v in row) + " |" for s, row in h5[f"p_escape_{n}"].items()]
    return out + [""]


def gates(g: dict) -> list[str]:
    out = [
        "## 6. Validity gates (SPEC §5; M3 result, PREREG §6)",
        "",
        "| Gate | Metric | Threshold | Status |",
        "|---|---|---|---|",
    ]
    out += [f"| {k} | {v['metric']:.4g} | {v['threshold']:.4g} | {'passed' if v['passed'] else '**FAILED**'} |"
            for k, v in g.items()]  # fmt: skip
    return out + ["", f"G6 failed (9 of 11 variants passed): **“{G6_SENTENCE}.”** Both failed variants (D41) are "
                  "×0.5 weakening (`r_max_sugar × 0.5`, `w_syn × 0.5`); the network is silent, with no sign reversal. Gate thresholds "
                  "were not changed after viewing results. Gates were computed before the decoder switched to integer steps (E13) and were not "
                  "recomputed. Details: `reports/gates.md`.", ""]  # fmt: skip


def tables_section(t: dict | None, figs: dict) -> list[str]:
    out = ["## 7. Psychometrics and calibration (RQ3, RQ4; table mode, PREREG §7)", ""]
    if not t:
        return out + [MISSING, ""]
    out += ["| Table | Rows | Queried (excluding copies) | Retried | Passes |", "|---|---|---|---|---|"]
    out += [
        f"| `{n}` | {r['rows']} | {r['queried']} | {r['retried']} | {r['sessions']} |" for n, r in t["rows"].items()
    ]
    missing = [f"jev_{m}" for m in analyses.JEV_MODES if f"jev_{m}" not in t["available"]]
    if missing or "connectome" not in t["available"]:
        out += ["", f"**Incomplete or missing tables are excluded from analysis:** {', '.join(missing) or '—'}"
                f"{'' if 'connectome' in t['available'] else ', connectome'}."]  # fmt: skip
    psy = t["psychometrics"]
    for key, title in (("escape_vs_looming", "p_escape(looming)"), ("eat_vs_bitter", "p_eat(bitter)")):
        out += [
            "",
            f"Logistic fit to the **{title}** slice:",
            "",
            "| Arbiter | Threshold x0 | Slope k | Note |",
            "|---|---|---|---|",
        ]
        for n, r in psy[key].items():
            th = "—" if r["threshold"] is None else f"{r['threshold']:.3f}"
            k = "—" if r["slope"] is None else f"{r['slope']:.2f}"
            note = "step: midpoint between nodes" if r["degenerate"] else ""
            if r["threshold"] is not None and not 0 <= r["threshold"] <= 1:
                note = "threshold outside stimulus range [0, 1]: fit extrapolation"
            out.append(f"| `{n}` | {th} | {k} | {note} |")
    out += ["", "Mean Jensen–Shannon divergence across grid B (base 2):", "", "| Pair | JS |", "|---|---|"]
    out += [f"| {k} | {v:.4f} |" for k, v in psy["js_mean"].items()]
    out += [
        "",
        "Service stability over time — JS between pass 1 and pass 2 policies (≥ 12 h):",
        "",
        "| Mode | JS |",
        "|---|---|",
    ]
    out += [f"| `{n}` | {'one pass' if v is None else f'{v:.4f}'} |" for n, v in t["sessions_js"].items()]
    out += _fig(figs.get("psychometric"), "Psychometric slices")
    out += _fig(figs.get("heatmaps"), "p_escape(sugar, looming) at bitter 0, hunger 0.5")
    out += ["### RQ4. Jev `p_escape` calibration against “ESCAPE is optimal according to the oracle”", "",
            "| Mode | Brier | Constant-prediction Brier (base rate) | Base rate | Predictions |", "|---|---|---|---|---|"]  # fmt: skip
    out += [f"| `{n}` | {c['brier']:.4f} | {c['brier_of_base_rate']:.4f} | {c['base_rate']:.3f} | {c['n']} |"
            for n, c in t["calibration"].items()]  # fmt: skip
    for n, c in t["calibration"].items():
        out += [
            "",
            f"Reliability table, `{n}`:",
            "",
            "| p interval | n | Mean p | Fraction labeled ESCAPE optimal |",
            "|---|---|---|---|",
        ]
        out += [
            f"| {r['bin']} | {r['n']} | {r['mean_p']:.3f} | {r['share_optimal']:.3f} |"
            for r in c["reliability"]
            if r["n"]
        ]
    return out + _fig(figs.get("reliability"), "Reliability diagram") + [""]


def time_section(d: dict[str, Any], figs: dict) -> list[str]:
    out = ["## 8. Decision time (RQ5; PREREG §8)", "",
           "`t_wall` is an operational measurement: for Jev it includes the network and OpenRouter hop; for the LIF "
           "connectome simulation it depends on this computer. These are not intrinsic model properties (SPEC §6.1). This project does not test TypeSafe's speed "
           "claims. `t_sim` is the simulated time to the decoder event.", "",
           "### 8.1 Protocol benchmark (`fob latency bench`, run by the author)", ""]  # fmt: skip
    if d["latency"] and d["latency"]["arbiters"]:
        from flight_or_bite.timing.bench import render

        runs = (d["latency"]["meta"] or {}).get("runs", [])
        out += [render(d["latency"]), ""] + [f"- run `{r['run_dir']}`: power “{r['throttle']['power']}”, timers "
                                             f"throttled: {'yes' if r['throttle']['timer_throttled'] else 'no'}, t_load "
                                             f"{r['t_load_s']}" for r in runs] + [""]  # fmt: skip
    else:
        out += [MISSING, ""]
    out += ["### 8.2 Decision latency in the main online run", ""]
    m = d["main"]
    if m:
        out += ["| Arbiter | n | t_wall p50, ms | p95, ms | t_sim p50 / p95, ms | RTF | Mean t_wall, ms | t_wall per episode, s |",
                "|---|---|---|---|---|---|---|---|"]  # fmt: skip
        for n, a in m["latency"].items():
            sim = f"{a['t_sim_p50_ms']:.1f} / {a['t_sim_p95_ms']:.1f}" if "rtf" in a else "—"
            rtf = f"{a['rtf']:.2f}" if "rtf" in a else "—"
            out.append(f"| `{n}` | {a['n']} | {a['p50_ms']:.3g} | {a['p95_ms']:.3g} | {sim} | {rtf} | "
                       f"{a['mean_ms']:.3g} | {a['per_episode_s']:.3g} |")  # fmt: skip
        out += _fig(figs.get("latency_ecdf"), "Decision-time ECDF")
        out += ["### 8.3 Deadline sweep: fraction of decisions meeting the deadline", ""]
        for track in ("wall", "native"):
            names = list(m["deadline_share"][track])
            out += [
                f"Track `{track}`:",
                "",
                "| Deadline, ms | " + " | ".join(f"`{n}`" for n in names) + " |",
                "|---|" + "---|" * len(names),
            ]
            out += [f"| {dl:g} | " + " | ".join(f"{m['deadline_share'][track][n][str(dl)]:.1%}" for n in names) + " |"
                    for dl in d["deadlines"]] + [""]  # fmt: skip
        out += _fig(
            figs.get("deadline_sweep"),
            "Deadline sweep, two tracks; oracle, fixed_priority, and random overlap when all their decisions meet the deadline",
        )
        out += _fig(figs.get("speed_vs_quality"), "Speed versus quality")
    else:
        out += [MISSING, ""]
    out += ["### 8.4 Chronometric hypothesis H6", ""]
    c = d["confirm"]
    if c:
        h = c["H6"]
        out += [f"Primary test (sugar delays the first DNp01 spike) — {_yes(h['confirmed'])}; paired Wilcoxon test "
                f"on H1 pairs with spikes in both arms; minimum p (Holm): {_p(h['min_p_holm'])}.", "",
                "| looming | Pairs | Median t_sim: control, ms | Condition, ms | Median difference, ms | p | p (Holm) |",
                "|---|---|---|---|---|---|---|"]  # fmt: skip
        out += [f"| {lv} | {x['n_pairs']} | {x['median_control_ms']:.1f} | {x['median_condition_ms']:.1f} | "
                f"{x['median_diff_ms']:+.1f} | {_p(x['p'])} | {_p(x['p_holm'])} |" for lv, x in h["levels"].items()
                if x["n_pairs"]] + [""]  # fmt: skip
    else:
        out += [MISSING, ""]
    t = d["tables"] or {}
    if "h6_secondary_connectome" in t:
        r = t["h6_secondary_connectome"]
        out += [f"Secondary analysis (LIF connectome simulation): Spearman ρ between d and median node `t_sim` = "
                f"**{r['rho']:+.3f}**, 95% CI {_ci(r['ci95'], '+.3f')}; {r['n_points']} nodes (IDLE trials excluded, "
                "p_eat + p_escape ≥ 0.5).", ""]  # fmt: skip
    if "h6_jev" in t:
        r = t["h6_jev"]
        out += [f"Jev (`informed`), equivalence: ρ between d and median node `t_wall` = **{r['rho']:+.3f}**, 95% CI "
                f"{_ci(r['ci95'], '+.3f')}; {r['n_points']} nodes. Equivalence bounds [−0.1, 0.1]: "
                f"**{'equivalence demonstrated' if r['equivalence_shown'] else 'equivalence not demonstrated'}**. "
                f"Additional (excluded from criterion): per-call ρ = {r['per_call_rho']:+.3f} (n = {r['per_call_n']}).", ""]  # fmt: skip
    return out + _fig(figs.get("chronometric"), "Chronometric curves") + [""]


def build(out_path: Path = OUT) -> Path:
    d = analyses.collect()
    figs = figures.make_all(d)
    parts = {"main online run (test)": d["main"], "secondary sampled run": d["sampled"],
             "H1–H4, H6, robustness": d["confirm"], "H5": d["h5"], "policy tables": d["tables"],
             "latency benchmark": d["latency"] and d["latency"]["arbiters"]}  # fmt: skip
    missing = [k for k, v in parts.items() if not v]
    lines = ["# Flight or Bite: final report", "",
             f"Built {datetime.now().astimezone().isoformat(timespec='minutes')} by `fob report` from artifacts only "
             "(no simulations or API calls). Preregistration: `PREREG.md` (frozen 2026-09-20); anything outside it "
             "is listed under Exploratory. Terminology: LIF simulation of the connectome, arbiter, policy; the connectome is "
             "a static map, and all dynamics are defined by the implementers (`docs/ENGINEERED.md`).", ""]  # fmt: skip
    if missing:
        lines += [f"> **INTERIM VERSION.** Artifacts not yet available: {'; '.join(missing)}.", ""]
    lines += main_metric(d["main"], "1. Primary metric (RQ2; PREREG §2): online, native action, test", True)
    lines += _fig(figs.get("survival"), "Survival curves")
    lines += main_metric(d["sampled"], "2. Secondary analysis: actions sampled from `probs` (100 episodes)", False)
    lines += (
        hypotheses(d["confirm"], d["h5"])
        + gates(d["gates"])
        + tables_section(d["tables"], figs)
        + time_section(d, figs)
    )
    ledger = d["ledger"] or {}
    lines += ["## 9. Questions not investigated and claims not made", "", "See `PREREG.md` §10; the list remains unchanged.", "",
              "## 10. Limitations and deviations", "",
              f"- G6 failed: “{G6_SENTENCE}” (section 6).",
              "- The main experiment called Jev through the alpha OpenRouter Decisions endpoint; Jev `t_wall` includes this hop (D12). Direct TypeSafe API timing was measured separately (D63–D64).",
              "- Jev and LIF connectome policy tables were built in the agent's process; their `t_wall` is not a protocol "
              "benchmark (used only for Jev H6 analysis). The author ran the section 8.1 benchmark and main online run (D5).",
              "- English edition (D65): translated after experiment completion at the author's request. Original frozen PREREG: `4a6f048`; pre-translation project: `02b66fc`. This is a post-freeze editorial deviation only; hypotheses, criteria, seeds, all 14 hashes, and raw results are unchanged.",
              "- Deviations from SPEC are listed in `docs/decisions.md` (D1–D65); manual assumptions are in `docs/ENGINEERED.md`.",
              f"- Jev calls used: {ledger.get('calls', '?')} of {ledger.get('max_calls', '?')}.",
              f"- Test-split accesses (lines in `runs/test_access.log`): {len(d['test_access'])}.", "",
              "Interpretations where PREREG is silent (committed before viewing tables and test results):", ""]  # fmt: skip
    lines += [f"- {r}" for r in d["readings"]]
    lines += [
        "",
        "## 11. Exploratory",
        "",
        "Non-confirmatory materials; no report conclusion relies on them:",
        "",
    ]
    lines += [f"- `reports/{name}`" for name in EXPLORATORY if (Path("reports") / name).is_file()]
    if Path("reports/latency_typesafe/comparison.md").is_file():
        lines += ["", "Additional benchmark after the main experiment (D63–D64): "
                  "[direct TypeSafe API versus OpenRouter](latency_typesafe/comparison.md). "
                  "The main report uses the original OpenRouter measurements; direct measurements are stored separately."]
    out_path.write_text("\n".join(lines) + "\n")
    return out_path
