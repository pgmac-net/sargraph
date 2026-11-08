"""Command line interface: ``sargraph graph`` (the default) and ``sargraph list``."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from . import plot
from .load import Loaded, filter_time, load_files, parse_when
from .model import SargraphError, Selector, select

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Graph sysstat SAR data (text or binary files) to png, svg or jpg.",
)

COMMANDS = {"graph", "list"}


def _fail(message: str) -> typer.Exit:
    typer.echo(f"sargraph: {message}", err=True)
    return typer.Exit(code=2)


def _load(files: list[Path]) -> Loaded:
    loaded = load_files(files)
    if loaded.data.empty:
        raise SargraphError("no SAR samples found in the given file(s)")
    return loaded


@app.command("list")
def list_metrics(
    files: Annotated[list[Path], typer.Argument(help="SAR file(s), text or binary.")],
) -> None:
    """List every available SECTION.COLUMN[@DEVICE] selector."""
    try:
        loaded = _load(files)
    except SargraphError as exc:
        raise _fail(str(exc)) from exc
    triples = loaded.data[["section", "metric", "device"]].drop_duplicates()
    for section, metric, device in sorted(triples.itertuples(index=False)):
        typer.echo(f"{section}.{metric}" + (f"@{device}" if device else ""))


@app.command("graph")
def graph(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    files: Annotated[list[Path], typer.Argument(help="SAR file(s), text or binary.")],
    metric: Annotated[
        list[str],
        typer.Option("--metric", "-m", help="SECTION.COLUMN[@DEVICE]; repeatable, globs allowed."),
    ],
    output: Annotated[
        list[str],
        typer.Option(
            "--output", "-o", help="Output file (.png/.svg/.jpg); repeatable; '-' = stdout."
        ),
    ],
    start: Annotated[
        str | None, typer.Option("--from", help="Start: ISO datetime, date, or HH:MM.")
    ] = None,
    stop: Annotated[
        str | None, typer.Option("--to", help="End (inclusive): ISO datetime, date, or HH:MM.")
    ] = None,
    layout: Annotated[
        str, typer.Option(help="stacked (default), combined or separate.")
    ] = "stacked",
    fmt: Annotated[
        str | None, typer.Option("--format", help="png, svg or jpg; required for '-o -'.")
    ] = None,
    width: Annotated[int, typer.Option(help="Image width in pixels.")] = 1600,
    height: Annotated[int, typer.Option(help="Image height in pixels.")] = 900,
    dpi: Annotated[int, typer.Option(help="Dots per inch.")] = 100,
    title: Annotated[str | None, typer.Option(help="Override the automatic title.")] = None,
) -> None:
    """Graph selected metrics from SAR files."""
    try:
        _graph(files, metric, output, start, stop, layout, fmt, width, height, dpi, title)
    except SargraphError as exc:
        raise _fail(str(exc)) from exc


def _graph(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    files: list[Path],
    metrics: list[str],
    outputs: list[str],
    start: str | None,
    stop: str | None,
    layout: str,
    fmt: str | None,
    width: int,
    height: int,
    dpi: int,
    title: str | None,
) -> None:
    if layout not in plot.LAYOUTS:
        raise SargraphError(f"unknown layout {layout!r} (use {', '.join(plot.LAYOUTS)})")
    if fmt is not None and fmt not in plot.FORMATS:
        raise SargraphError(f"unknown format {fmt!r} (use {', '.join(plot.FORMATS)})")
    selectors = [Selector.parse(m) for m in metrics]
    targets = [(o, fmt if o == "-" else plot.format_for(o)) for o in outputs]
    if any(o == "-" and fmt is None for o, _ in targets):
        raise SargraphError("'-o -' needs --format png|svg|jpg")
    if "-" in outputs and (len(outputs) > 1 or (layout == "separate" and len(selectors) > 1)):
        raise SargraphError("stdout output supports a single image only")

    loaded = _load(files)
    lo = parse_when(start, loaded.data, end=False) if start else None
    hi = parse_when(stop, loaded.data, end=True) if stop else None
    loaded = filter_time(loaded, lo, hi)

    groups = []
    for selector in selectors:
        rows = select(loaded.data, selector)
        if rows.empty:
            raise SargraphError(f"no data matches {selector} in the chosen time range")
        groups.append(plot.Group(selector, rows))

    opts = plot.Options(layout=layout, width=width, height=height, dpi=dpi, title=title)
    figures = plot.render(groups, loaded.restarts, opts)
    for out, out_fmt in targets:
        for index, (selector, fig) in enumerate(figures, start=1):
            if out == "-":
                plot.save(fig, sys.stdout.buffer, out_fmt or "png")
                continue
            name = (
                plot.expand_pattern(out, index, selector, len(figures))
                if (layout == "separate")
                else out
            )
            plot.save(fig, name, out_fmt or "png")


def main() -> None:
    """Entry point: ``graph`` is the default command when none is given."""
    args = sys.argv[1:]
    if args and args[0] not in COMMANDS and args[0] not in ("--help", "-h"):
        sys.argv.insert(1, "graph")
    app()


if __name__ == "__main__":
    main()
