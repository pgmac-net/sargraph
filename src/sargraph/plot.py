"""Build figures from selected series and export them as png, svg or jpg."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import matplotlib.dates as mdates
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .model import SargraphError, Selector

LAYOUTS = ("stacked", "combined", "separate")
EXTENSIONS = {".png": "png", ".svg": "svg", ".jpg": "jpg", ".jpeg": "jpg"}
FORMATS = ("png", "svg", "jpg")
JPG_QUALITY = 90


@dataclass(frozen=True)
class Options:
    """Figure options shared by every layout."""

    layout: str = "stacked"
    width: int = 1600
    height: int = 900
    dpi: int = 100
    title: str | None = None


@dataclass(frozen=True)
class Group:
    """The rows chosen by one ``-m`` selector."""

    selector: Selector
    rows: pd.DataFrame


def format_for(path: str) -> str:
    """Output format from a file extension."""
    ext = Path(path).suffix.lower()
    if ext not in EXTENSIONS:
        raise SargraphError(f"{path}: unsupported extension {ext!r} (use .png, .svg, .jpg)")
    return EXTENSIONS[ext]


def _series(group: Group, multi_host: bool, full: bool) -> list[tuple[str, pd.DataFrame]]:
    """Split a group into one labelled frame per (host, section, metric, device)."""
    out = []
    keys = ["host", "section", "metric", "device"]
    for (host, section, metric, device), part in group.rows.groupby(keys, sort=True):
        label = f"{section}.{metric}" if full else metric
        if device:
            label += f"@{device}"
        if multi_host:
            label = f"{host}:{label}"
        out.append((label, part.assign(_host=host)))
    return out


def _draw(
    ax: Axes,
    group: Group,
    restarts: pd.DataFrame,
    multi_host: bool,
    full: bool,
) -> None:
    for label, part in _series(group, multi_host, full):
        points = part.set_index("timestamp")["value"].sort_index()
        host = part["_host"].iloc[0]
        gaps = restarts[restarts["host"] == host]["timestamp"]
        gaps = gaps[(gaps > points.index.min()) & (gaps < points.index.max())]
        if len(gaps):
            points = pd.concat([points, pd.Series(float("nan"), index=gaps)]).sort_index()
        ax.plot(points.index, points.to_numpy(), label=label, linewidth=1.2)


def _finish_axes(ax: Axes, ylabel: str | None) -> None:
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.grid(True, alpha=0.3)
    if ylabel:
        ax.set_ylabel(ylabel)
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="upper right", fontsize="small", ncols=2 if len(ax.lines) > 6 else 1)


def _figure(width: int, height: int, dpi: int) -> Figure:
    return Figure(figsize=(width / dpi, height / dpi), dpi=dpi, layout="constrained")


def _title(groups: list[Group], override: str | None, hosts: list[str]) -> str:
    if override:
        return override
    names = ", ".join(str(g.selector) for g in groups)
    return f"{names} ({', '.join(hosts)})"


def render(
    groups: list[Group], restarts: pd.DataFrame, opts: Options
) -> list[tuple[Selector | None, Figure]]:
    """Build figures. ``stacked`` and ``combined`` give one; ``separate`` one per group."""
    if opts.layout not in LAYOUTS:
        raise SargraphError(f"unknown layout {opts.layout!r}")
    hosts = sorted({h for g in groups for h in g.rows["host"].unique()})
    multi_host = len(hosts) > 1

    if opts.layout == "separate":
        figures = []
        for group in groups:
            fig = _figure(opts.width, opts.height, opts.dpi)
            ax = fig.add_subplot()
            _draw(ax, group, restarts, multi_host, full=True)
            _finish_axes(ax, group.selector.column)
            ax.set_title(opts.title or f"{group.selector} ({', '.join(hosts)})")
            figures.append((group.selector, fig))
        return figures

    fig = _figure(opts.width, opts.height, opts.dpi)
    fig.suptitle(_title(groups, opts.title, hosts))
    if opts.layout == "combined":
        ax = fig.add_subplot()
        for group in groups:
            _draw(ax, group, restarts, multi_host, full=True)
        columns = {g.selector.column for g in groups}
        _finish_axes(ax, columns.pop() if len(columns) == 1 else None)
        return [(None, fig)]

    axes = fig.subplots(len(groups), 1, sharex=True, squeeze=False)[:, 0]
    for ax, group in zip(axes, groups, strict=True):
        _draw(ax, group, restarts, multi_host, full=False)
        ax.set_title(str(group.selector), fontsize="small", loc="left")
        _finish_axes(ax, group.selector.column)
    return [(None, fig)]


def safe_name(selector: Selector) -> str:
    """Selector as a filename-safe string."""
    return re.sub(r"[^A-Za-z0-9._@-]+", "_", str(selector))


def expand_pattern(pattern: str, index: int, selector: Selector | None, total: int) -> str:
    """Fill ``{n}`` and ``{metric}`` in an output name for the ``separate`` layout."""
    has_placeholder = "{n}" in pattern or "{metric}" in pattern
    if total > 1 and not has_placeholder:
        raise SargraphError(
            f"{pattern}: layout 'separate' writes {total} files; "
            "put {n} or {metric} in the output name"
        )
    metric = safe_name(selector) if selector else ""
    return pattern.replace("{n}", str(index)).replace("{metric}", metric)


def save(fig: Figure, target: str | BinaryIO, fmt: str) -> None:
    """Write a figure. jpg gets a white background (no transparency) at quality 90."""
    kwargs: dict = {"format": fmt, "facecolor": "white"}
    if fmt == "jpg":
        kwargs["pil_kwargs"] = {"quality": JPG_QUALITY}
    fig.savefig(target, **kwargs)
