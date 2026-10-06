"""Static PNG figures of the final report (SPEC §9). One fixed colour per arbiter, everywhere."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

FIG = Path("reports/figures")
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
# colour follows the entity, never its rank; validated with the dataviz palette validator (light surface)
COLOR = {"connectome": "#2a78d6", "jev_informed": "#eb6834", "oracle": "#1baf7a", "fixed_priority": "#eda100",
         "random": "#e87ba4", "jev_naive": "#008300", "jev_informed_bucketed": "#4a3aa7", "jev_bucketed": "#e34948"}  # fmt: skip
MARKER = {"connectome": "o", "jev_informed": "s", "oracle": "^", "fixed_priority": "D", "random": "v",
          "jev_naive": "P", "jev_informed_bucketed": "X", "jev_bucketed": "*"}  # fmt: skip
SEQ = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#6da7ec", "#256abf", "#0d366b"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "font.size": 10,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.labelcolor": INK2, "ytick.labelcolor": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 11, "axes.titlecolor": INK,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False, "lines.linewidth": 2,
    "lines.markersize": 7, "axes.axisbelow": True,
})  # fmt: skip


def _save(fig, name: str) -> str:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return f"figures/{name}"


def _style(name: str) -> dict[str, Any]:
    return {"color": COLOR[name], "marker": MARKER[name], "markeredgecolor": SURFACE, "markeredgewidth": 1.5}


def speed_vs_quality(main: dict) -> str:
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    for n, row in main["arbiters"].items():
        lat, pct, ci = main["latency"][n], row["percent_of_oracle"], row["percent_of_oracle_ci95"]
        xs = [("t_wall", lat["p50_ms"], lat["p50_ci95"])]
        if "t_sim_p50_ms" in lat:
            xs.append(("t_sim", lat["t_sim_p50_ms"], None))
        for kind, x, xci in xs:
            ax.errorbar(x, 100 * pct, yerr=[[100 * (pct - ci[0])], [100 * (ci[1] - pct)]],
                        xerr=None if xci is None else [[x - xci[0]], [xci[1] - x]], color=COLOR[n], marker=MARKER[n],
                        mfc=COLOR[n] if kind == "t_wall" else SURFACE, mec=COLOR[n], capsize=3, lw=1.5, ls="none")  # fmt: skip
            ax.annotate(f"{n} ({kind})" if len(xs) > 1 else n, (x, 100 * pct), xytext=(7, 6 if kind == "t_wall" else -14),
                        textcoords="offset points", color=INK2, fontsize=9)  # fmt: skip
    ax.set_xscale("log")
    ax.set_xlabel("Decision t_wall p50, ms (log scale); connectome t_sim p50: open marker")
    ax.set_ylabel("% of oracle")
    ax.set_title("Speed versus quality: main online run, test")
    return _save(fig, "speed_vs_quality.png")


def latency_ecdf(main: dict) -> str:
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for n, wall in main["walls_ms"].items():
        x = np.sort(wall)
        ax.plot(x, np.arange(1, len(x) + 1) / len(x), color=COLOR[n], label=f"{n}, t_wall")
        if n in main["sims_ms"]:
            s = np.sort(main["sims_ms"][n])
            ax.plot(s, np.arange(1, len(s) + 1) / len(s), color=COLOR[n], ls="--", label=f"{n}, t_sim")
    ax.set_xscale("log")
    ax.set_xlabel("Decision time, ms (log scale)")
    ax.set_ylabel("Fraction of decisions")
    ax.set_title("Decision-time ECDF: main online run")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    return _save(fig, "latency_ecdf.png")


def deadline_sweep(main: dict) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=True)
    for ax, track in zip(axes, ("wall", "native"), strict=True):
        for n, shares in main["deadline_share"][track].items():
            ax.plot([float(d) for d in shares], list(shares.values()), label=n, **_style(n))
        ax.set_xscale("log")
        ax.set_xlabel("Deadline, ms (log scale)")
        ax.set_title({"wall": "Wall track: all use t_wall", "native": "Native track: connectome uses t_sim"}[track])
    axes[0].set_ylabel("Fraction of decisions meeting deadline")
    axes[1].legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    return _save(fig, "deadline_sweep.png")


def survival(main: dict) -> str:
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for n, life in main["lifetimes"].items():
        life = np.asarray(life)
        t = np.arange(0, int(life.max()) + 2)
        ax.step(t, [(life >= k).mean() for k in t], where="post", color=COLOR[n], label=n)
    ax.set_xlabel("Trial")
    ax.set_ylabel("Fraction of episodes surviving to trial")
    ax.set_title("Survival curves: main online run")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    return _save(fig, "survival.png")


def chronometric(tables: dict) -> str | None:
    panels = [(k, t) for k, t in (("h6_secondary_connectome", "connectome: median node t_sim, ms"),
                                  ("h6_jev", "jev_informed: median node t_wall, ms")) if k in tables]  # fmt: skip
    if not panels:
        return None
    fig, axes = plt.subplots(1, len(panels), figsize=(5.3 * len(panels), 4.2), squeeze=False)
    for ax, (key, title) in zip(axes[0], panels, strict=True):
        pts = np.array(tables[key]["points"])
        name = "connectome" if "connectome" in key else "jev_informed"
        if len(pts):
            ax.scatter(pts[:, 0], pts[:, 1], s=14, color=COLOR[name], alpha=0.55, edgecolors="none")
        ax.set_xlabel("Conflict difficulty d = 1 − |p_escape − p_eat|")
        ax.set_title(title)
    return _save(fig, "chronometric.png")


def psychometric(tables: dict) -> str:
    psy = tables["psychometrics"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=True)
    for ax, key, x, xl in ((axes[0], "escape_vs_looming", psy["x_looming"], "looming (sugar 0, bitter 0, hunger 0.5)"),
                           (axes[1], "eat_vs_bitter", psy["x_bitter"], "bitter (sugar 0.667, looming 0, hunger 0.5)")):  # fmt: skip
        for n, r in psy[key].items():
            ax.plot(x, r["p"], label=n, **_style(n))
        ax.set_xlabel(xl)
        ax.set_title({"escape_vs_looming": "p_escape(looming)", "eat_vs_bitter": "p_eat(bitter)"}[key])
    axes[0].set_ylabel("Probability")
    axes[1].legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    return _save(fig, "psychometric.png")


def heatmaps(tables: dict) -> str:
    psy = tables["psychometrics"]
    names = [n for n in ("connectome", "jev_informed", "oracle") if n in psy["heatmaps"]]
    fig, axes = plt.subplots(1, len(names), figsize=(4.0 * len(names) + 0.8, 3.9), squeeze=False)
    for ax, n in zip(axes[0], names, strict=True):
        z = np.array(psy["heatmaps"][n])  # [sugar, looming]
        im = ax.imshow(z, origin="lower", cmap=SEQ, vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(range(z.shape[1]), [f"{v:.2f}" for v in psy["x_looming"]], fontsize=8)
        ax.set_yticks(range(z.shape[0]), [f"{v:.2f}" for v in psy["x_sugar"]], fontsize=8)
        for (i, j), v in np.ndenumerate(z):
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7, color=SURFACE if v > 0.5 else INK)
        ax.set_xlabel("looming")
        ax.set_title(n)
        ax.grid(False)
    axes[0][0].set_ylabel("sugar")
    fig.colorbar(im, ax=axes[0].tolist(), label="p_escape (bitter 0, hunger 0.5)", fraction=0.03, pad=0.02)
    return _save(fig, "heatmaps_p_escape.png")


def reliability(tables: dict) -> str | None:
    if not tables["calibration"]:
        return None
    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    ax.plot([0, 1], [0, 1], color=MUTED, lw=1, ls=":", label="Perfect calibration")
    for n, c in tables["calibration"].items():
        rel = [r for r in c["reliability"] if r["n"]]
        ax.plot([r["mean_p"] for r in rel], [r["share_optimal"] for r in rel], label=n, **_style(n))
    ax.set_xlabel("Jev p_escape (mean within bin)")
    ax.set_ylabel("Fraction of nodes where oracle chooses ESCAPE")
    ax.set_title("Reliability diagram (RQ4)")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    return _save(fig, "reliability.png")


def make_all(data: dict[str, Any]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    if data["main"]:
        out |= {"speed_vs_quality": speed_vs_quality(data["main"]), "latency_ecdf": latency_ecdf(data["main"]),
                "deadline_sweep": deadline_sweep(data["main"]), "survival": survival(data["main"])}  # fmt: skip
    if data["tables"]:
        out |= {"chronometric": chronometric(data["tables"]), "psychometric": psychometric(data["tables"]),
                "heatmaps": heatmaps(data["tables"]), "reliability": reliability(data["tables"])}  # fmt: skip
    return out
