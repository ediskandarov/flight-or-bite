"""The `fob` command (SPEC §9). M0: skeleton, `fob info`, and the Jev smoke test."""

from __future__ import annotations

from enum import StrEnum

import typer
from dotenv import find_dotenv, load_dotenv
from rich.console import Console
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
    resolve_backend,
)
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


class BenchArbiter(StrEnum):
    jev = "jev"
    connectome = "connectome"
    all = "all"


class Split(StrEnum):
    dev = "dev"
    test = "test"


class JevBackendName(StrEnum):
    auto = "auto"
    typesafe = "typesafe"
    openrouter = "openrouter"


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
def fetch_data() -> None:
    """Download the connectome and verify checksums."""
    _not_implemented("fetch-data", "M1")


@app.command()
def perf() -> None:
    """Benchmark LIF backends -> reports/perf.md."""
    _not_implemented("perf", "M1")


@app.command()
def gate(name: str = typer.Argument(..., help="Gate id, G1..G7.")) -> None:
    """Run one validity gate."""
    _not_implemented(f"gate {name}", "M1 (G1) / M3")


@app.command()
def gates() -> None:
    """Run all validity gates and print a pass/fail summary."""
    _not_implemented("gates", "M3")


@table_app.command("build")
def table_build(arbiter: TableArbiter = typer.Option(..., "--arbiter")) -> None:
    """Build a policy table (resumable)."""
    _not_implemented("table build", "M4")


@table_app.command("show")
def table_show(
    arbiter: str = typer.Option(..., "--arbiter"),
    slice_: str = typer.Option("looming", "--slice"),
) -> None:
    """Show a policy and latency slice."""
    _not_implemented("table show", "M4")


@latency_app.command("bench")
def latency_bench(
    arbiter: BenchArbiter = typer.Option(..., "--arbiter"),
    n: int = typer.Option(1000, "--n"),
) -> None:
    """Measure decision time following the SPEC §6.2 protocol."""
    _not_implemented("latency bench", "M4")


@latency_app.command("show")
def latency_show() -> None:
    """Show p50/p90/p99 and terminal histograms."""
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
) -> None:
    """Evaluate arbiters; table with confidence intervals."""
    _not_implemented("eval", "M2 (dev) / M5 (test)")


@app.command()
def replay(
    seed: int = typer.Option(..., "--seed"),
    arbiter: str = typer.Option(..., "--arbiter"),
) -> None:
    """Text log of a tabular episode."""
    _not_implemented("replay", "M4")


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


def _fmt_ms(ns: int | None) -> str:
    return "-" if ns is None else f"{ns / 1e6:.1f}"


@jev_app.command("smoke")
def jev_smoke(
    n: int = typer.Option(20, "--n", min=1),
    mock: bool = typer.Option(False, "--mock", help="Use MockJevClient instead of the network."),
    mock_latency_ms: float = typer.Option(50.0, "--mock-latency-ms", min=0.0),
    max_calls: int = typer.Option(DEFAULT_MAX_CALLS, "--max-calls", min=0),
    backend: JevBackendName = typer.Option(JevBackendName.auto, "--backend"),
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
            resolved = resolve_backend(backend.value)
            client, backend_name = JevClient(backend=resolved, max_calls=max_calls), resolved.name
    except JevAuthError as e:
        console.print(f"[red]{e}[/] (or pass --mock)")
        raise typer.Exit(1) from e

    table = Table(title=f"Jev smoke test, n={n}, backend={backend_name}")
    for col in ("#", "model", "choice", "probabilities", "connect ms", "ttfb ms", "total ms"):
        table.add_column(col, justify="left" if col in ("model", "probabilities") else "right")

    totals: list[int] = []
    distinct: set[tuple[tuple[str, float], ...]] = set()
    cost_usd = 0.0
    try:
        for i in range(n):
            resp = client.evaluate(_SMOKE_STATE, {"action": _SMOKE_QUESTION})
            ans = resp.choice("action")
            totals.append(resp.timings.total_ns)
            distinct.add(tuple(sorted(ans.probabilities.items())))
            cost_usd += resp.meta.get("cost_usd") or 0.0
            # The API returns options in arbitrary order; print them in ours.
            probs = "  ".join(
                f"{k} {ans.probabilities.get(k, float('nan')):.2f}"
                for k in _SMOKE_QUESTION.criteria
            )
            table.add_row(
                str(i), resp.model, ans.choice, probs,
                _fmt_ms(resp.timings.connect_ns), _fmt_ms(resp.timings.ttfb_ns),
                _fmt_ms(resp.timings.total_ns),
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
        f"p50 {s.p50_ms:.1f}  p90 {s.p90_ms:.1f}  p99 {s.p99_ms:.1f} ms | "
        f"budget used {client.budget.used}/{client.budget.max_calls}",
        soft_wrap=True,
    )
    # All requests are identical, so this doubles as a determinism check.
    console.print(
        f"distinct probability vectors over {s.n} identical requests: {len(distinct)} | "
        f"reported cost: ${cost_usd:.6f}",
        soft_wrap=True,
    )
