"""The `fob` command (SPEC §9). M0: skeleton, `fob info`, and the Jev smoke test."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import httpx
import typer
from dotenv import find_dotenv, load_dotenv
from rich.console import Console
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TransferSpeedColumn
from rich.table import Table

from flight_or_bite import __version__, sysinfo
from flight_or_bite.arbiters.jev_client import (
    DEFAULT_MAX_CALLS,
    ChoiceQuestion,
    JevAuthError,
    JevClient,
    JevClientProtocol,
    JevError,
    MockJevClient,
)
from flight_or_bite.lif import data as lif_data
from flight_or_bite.timing.timers import summarize_ns
from flight_or_bite.types import Action

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Flight or Bite CLI.")
table_app = typer.Typer(no_args_is_help=True, help="Policy tables.")
latency_app = typer.Typer(no_args_is_help=True, help="Decision-time measurements.")
jev_app = typer.Typer(no_args_is_help=True, help="Jev API utilities.")
app.add_typer(table_app, name="table")
app.add_typer(latency_app, name="latency")
app.add_typer(jev_app, name="jev")

console = Console()

EXIT_NOT_IMPLEMENTED = 3  # 2 is taken: click uses it for usage errors


def _not_implemented(command: str, milestone: str) -> None:
    console.print(f"[yellow]`fob {command}` is not implemented yet (planned for {milestone}).[/]")
    raise typer.Exit(EXIT_NOT_IMPLEMENTED)


class TableArbiter(StrEnum):
    connectome = "connectome"
    shuffled = "shuffled"
    jev = "jev"
    oracle = "oracle"
    fixed_priority = "fixed_priority"
    random = "random"


class BenchArbiter(StrEnum):
    jev = "jev"
    connectome = "connectome"
    all = "all"


class Split(StrEnum):
    dev = "dev"
    test = "test"


def _load_env() -> None:
    """Read API keys from a .env in the working directory; real environment variables win."""
    load_dotenv(find_dotenv(usecwd=True))


@app.command()
def info() -> None:
    """Print version and host description (chip, cores, memory)."""
    host = sysinfo.collect()
    table = Table(title=f"flight-or-bite {__version__}", show_header=False)
    for key, value in host.as_dict().items():
        table.add_row(key, str(value))
    table.add_row("default_workers", str(host.default_workers))
    console.print(table)


@app.command("fetch-data")
def fetch_data(
    version: list[int] = typer.Option(None, "--version", help="Connectome version; repeatable."),
    data_dir: Path = typer.Option(Path("data"), "--data-dir"),
    config: Path = typer.Option(Path("configs/data.yaml"), "--config"),
) -> None:
    """Download the connectome and verify checksums."""
    manifest = lif_data.load_manifest(config)
    files = lif_data.select(manifest, version or {f.version for f in manifest.files})
    columns = (
        TextColumn("{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
    )
    try:
        with Progress(*columns, console=console) as progress, httpx.Client(timeout=60.0) as client:
            for file in files:
                task = progress.add_task(file.name, total=file.bytes)
                _, downloaded = lif_data.fetch_file(
                    manifest, file, data_dir, client, lambda n, t=task: progress.advance(t, n)
                )
                if not downloaded:
                    progress.update(task, completed=file.bytes, description=f"{file.name} (cached)")
    except (httpx.HTTPError, lif_data.ChecksumError) as e:
        console.print(f"[red]fetch-data failed: {e}[/]")
        raise typer.Exit(1) from e
    console.print(
        f"[green]{len(files)} file(s) verified[/] against {manifest.source.repo}"
        f"@{manifest.source.commit[:10]} in {data_dir}/ — data licence: "
        f"{manifest.source.data_license}; do not commit or redistribute.",
        soft_wrap=True,
    )


@app.command()
def perf(
    backend: list[str] = typer.Option(None, "--backend", help="Repeatable; default: all."),
    version: int = typer.Option(None, "--version", help="Connectome version; default: lif.yaml."),
    n_full: int = typer.Option(10, "--n-full", min=1),
    n_stop: int = typer.Option(10, "--n-stop", min=1),
    out: Path = typer.Option(Path("reports/perf.md"), "--out"),
) -> None:
    """Benchmark LIF backends -> reports/perf.md."""
    from flight_or_bite.lif.perf_report import run_perf

    run_perf(console, backend or None, version, n_full, n_stop, out)


@app.command()
def gate(name: str = typer.Argument(..., help="Gate id, G1..G7.")) -> None:
    """Run one validity gate (protocol: configs/gates.yaml)."""
    from flight_or_bite.validation import run_gates

    if name.upper() not in run_gates.GATES:
        console.print(f"[red]unknown gate {name!r}; expected one of {', '.join(run_gates.GATES)}[/]")
        raise typer.Exit(2)
    run_gates.run(console, [name.upper()])


@app.command()
def gates(
    only_summary: bool = typer.Option(False, "--summary", help="Print the table, run nothing."),
) -> None:
    """Run all validity gates and print a pass/fail summary."""
    from flight_or_bite.validation import run_gates

    ok = run_gates.summary(console) if only_summary else run_gates.run(console, list(run_gates.GATES))
    raise typer.Exit(0 if ok else 1)


def _run(op, *args) -> None:
    from flight_or_bite.policy_table.cli_ops import NotReady

    try:
        op(console, *args)
    except NotReady as e:
        console.print(f"[yellow]{e}[/]")
        raise typer.Exit(EXIT_NOT_IMPLEMENTED) from e


@table_app.command("build")
def table_build(
    arbiter: TableArbiter = typer.Option(..., "--arbiter"),
    mode: str = typer.Option(None, "--mode", help="Jev state mode: naive, informed, bucketed."),
    mock: bool = typer.Option(False, "--mock", help="Jev: use MockJevClient (no network)."),
    grid: Path = typer.Option(Path("configs/grid.yaml"), "--grid"),
    session: int = typer.Option(1, "--session", help="Jev: pass 1 or 2, 12 h apart (PREREG §7)."),
) -> None:
    """Build a policy table (resumable)."""
    from flight_or_bite.policy_table import cli_ops

    if arbiter is TableArbiter.jev and not mock:
        _load_env()
    _run(cli_ops.table_build, arbiter.value, mode, mock, grid, session)


@table_app.command("show")
def table_show(
    arbiter: str = typer.Option(..., "--arbiter", help="Table name under reports/tables/."),
    slice_: str = typer.Option("looming", "--slice"),
    at: list[str] = typer.Option(None, "--at", help="Fix another axis, e.g. --at sugar=0.6"),
) -> None:
    """Show a policy and latency slice."""
    from flight_or_bite.policy_table import cli_ops

    fixed = {k: float(v) for k, v in (item.split("=", 1) for item in at or [])}
    _run(cli_ops.table_show, arbiter, slice_, fixed)


@latency_app.command("bench")
def latency_bench(
    arbiter: BenchArbiter = typer.Option(..., "--arbiter"),
    n: int = typer.Option(1000, "--n"),
) -> None:
    """Measure decision time following the SPEC §6.2 protocol."""
    _not_implemented("latency bench", "M4")


@latency_app.command("show")
def latency_show() -> None:
    """Show p50/p95 and terminal histograms."""
    _not_implemented("latency show", "M4")


@app.command()
def live(seed: int = typer.Option(..., "--seed")) -> None:
    """Live episode: both arbiters online on the same stimuli."""
    _not_implemented("live", "M4")


@app.command("eval")
def eval_(
    split: Split = typer.Option(..., "--split"),
    unlock_test: bool = typer.Option(False, "--unlock-test"),
    deadline_sweep: bool = typer.Option(False, "--deadline-sweep"),
    online: bool = typer.Option(False, "--online", help="Main metric: paired online episodes (PREREG §2)."),
    episodes: int = typer.Option(None, "--episodes", help="Default: 300, or 100 with --sample-from-probs."),
    sample: bool = typer.Option(False, "--sample-from-probs", help="Secondary analysis (PREREG §2)."),
    out: Path = typer.Option(None, "--out", help="Default: reports/online/<split>[_sampled]."),
    mock_jev: bool = typer.Option(False, "--mock-jev", help="Offline: MockJevClient instead of the network."),
) -> None:
    """Evaluate arbiters; table with confidence intervals. With --online: the main metric."""
    from flight_or_bite.arena.env import SplitLocked

    try:
        if online:
            from flight_or_bite.eval import online as online_eval

            if not mock_jev:
                _load_env()
            try:
                where = online_eval.run_online(console, split.value, episodes, unlock_test, sample, out,
                                               mock_jev=mock_jev)  # fmt: skip
            except online_eval.RunStopped as e:
                console.print(f"[red]{e}[/]")
                raise typer.Exit(1) from e
            s = online_eval.summary_of(where)
            for name, r in s["arbiters"].items():
                console.print(
                    f"  {name:16s} {r['lifetime_mean']:6.1f} [{r['lifetime_ci95'][0]:.1f}, {r['lifetime_ci95'][1]:.1f}]"
                )
            console.print(f"[green]{s['episodes']} paired episodes in {where}[/]")
        else:
            from flight_or_bite.eval.run_eval import run_eval

            run_eval(console, split.value, unlock_test, deadline_sweep)
    except SplitLocked as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1) from e


@app.command()
def replay(
    seed: int = typer.Option(..., "--seed"),
    arbiter: str = typer.Option(..., "--arbiter"),
) -> None:
    """Text log of a tabular episode (or of a baseline played directly)."""
    from flight_or_bite.policy_table import cli_ops

    _run(cli_ops.replay, seed, arbiter)


@app.command()
def report() -> None:
    """Assemble reports/final_report.md and figures from artifacts."""
    _not_implemented("report", "M5")


# Smoke-test request only. Experiment prompts live in configs/jev_prompts/ (tuned on dev, M4).
_SMOKE_STATE = {"sugar": 0.7, "bitter": 0.05, "looming": 0.6, "hunger": 0.5}
_SMOKE_QUESTION = ChoiceQuestion(
    instructions="Which action should the agent take?",
    criteria={a.value: None for a in Action},
)


@jev_app.command("smoke")
def jev_smoke(
    n: int = typer.Option(20, "--n", min=1),
    mock: bool = typer.Option(False, "--mock", help="Use MockJevClient instead of the network."),
    mock_latency_ms: float = typer.Option(50.0, "--mock-latency-ms", min=0.0),
    max_calls: int = typer.Option(DEFAULT_MAX_CALLS, "--max-calls", min=0),
) -> None:
    """Identical sequential calls over one keep-alive session, printing per-call latency."""
    client: JevClientProtocol
    try:
        if mock:
            client, backend_name = (
                MockJevClient(latency_s=mock_latency_ms / 1e3, max_calls=max_calls),
                "mock",
            )
        else:
            _load_env()
            client, backend_name = JevClient(max_calls=max_calls), "openrouter-decisions"
    except JevAuthError as e:
        console.print(f"[red]{e}[/] (or pass --mock)")
        raise typer.Exit(1) from e

    table = Table(title=f"Jev smoke test, n={n}, backend={backend_name}")
    for col in ("#", "model", "choice", "probabilities", "t_wall ms"):
        table.add_column(col, justify="left" if col in ("model", "probabilities") else "right")

    totals: list[int] = []
    distinct: set[tuple[tuple[str, float], ...]] = set()
    cost_usd = 0.0
    try:
        for i in range(n):
            resp = client.evaluate(_SMOKE_STATE, {"action": _SMOKE_QUESTION})
            ans = resp.choice("action")
            totals.append(resp.t_wall_ns)
            distinct.add(tuple(sorted(ans.probabilities.items())))
            cost_usd += resp.meta.get("cost_usd") or 0.0
            # The API returns options in arbitrary order; print them in ours.
            probs = "  ".join(f"{k} {ans.probabilities.get(k, float('nan')):.2f}" for k in _SMOKE_QUESTION.criteria)
            table.add_row(
                str(i), resp.model, ans.choice, probs, f"{resp.t_wall_ns / 1e6:.1f}",
            )  # fmt: skip
    except JevError as e:
        console.print(table)
        console.print(f"[red]call {len(totals)} failed: {e}[/]")
        raise typer.Exit(1) from e
    finally:
        client.close()

    console.print(table)
    s = summarize_ns(totals)
    console.print(
        f"cold first call: {totals[0] / 1e6:.1f} ms | all {s.n} calls: "
        f"p50 {s.p50_ms:.1f}  p95 {s.p95_ms:.1f} ms | "
        f"budget used {client.budget.used}/{client.budget.max_calls} (all runs)",
        soft_wrap=True,
    )
    # All requests are identical, so this doubles as a determinism check.
    console.print(
        f"distinct probability vectors over {s.n} identical requests: {len(distinct)} | reported cost: ${cost_usd:.6f}",
        soft_wrap=True,
    )
