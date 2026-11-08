"""Load SAR files (text or binary), merge them and filter by time."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path

import pandas as pd

from .model import COLUMNS, KEY, RESTART_SECTION, SargraphError
from .parse_text import parse_text


@dataclass
class Loaded:
    """Parsed data plus the restart markers (used to break plotted lines)."""

    data: pd.DataFrame
    restarts: pd.DataFrame


def is_binary(path: Path) -> bool:
    """True if the file looks like a binary ``saDD`` file rather than text sar output."""
    with path.open("rb") as handle:
        head = handle.read(512)
    if b"\x00" in head:
        return True
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as exc:
        # A multi-byte character cut at the 512-byte boundary is still text.
        if exc.start < len(head) - 4:
            return True
    return False


def _run_sar(path: Path) -> str:
    """Render a binary sa file as text. ISO time keeps it 24h, local and locale-proof."""
    env = {**os.environ, "LC_ALL": "C", "S_TIME_FORMAT": "ISO"}
    try:
        result = subprocess.run(
            ["sar", "-A", "-f", str(path)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise SargraphError(
            f"{path}: binary sa file needs the 'sar' command (install sysstat)"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SargraphError(f"{path}: sar timed out reading the file") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or "unknown error"
        raise SargraphError(
            f"{path}: sar could not read the file ({detail}). "
            "If it was written by another sysstat version, convert it with 'sadf -c'."
        )
    return result.stdout


def load_file(path: Path) -> pd.DataFrame:
    """Parse one file into the long-format table."""
    if not path.is_file():
        raise SargraphError(f"{path}: no such file")
    if is_binary(path):
        return parse_text(_run_sar(path).splitlines())
    with path.open(encoding="utf-8", errors="replace") as handle:
        return parse_text(handle)


def load_files(paths: list[Path]) -> Loaded:
    """Load and merge files. Duplicate samples keep the first value seen."""
    frames = [load_file(p) for p in paths]
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    merged = merged.drop_duplicates(subset=KEY, keep="first")
    is_restart = merged["section"] == RESTART_SECTION
    return Loaded(
        data=merged[~is_restart].reset_index(drop=True),
        restarts=merged[is_restart][["host", "timestamp"]].reset_index(drop=True),
    )


def parse_when(text: str, data: pd.DataFrame, *, end: bool) -> datetime:
    """Parse ``--from``/``--to``: ISO datetime, date, or bare ``HH:MM[:SS]``.

    A bare time needs the data to cover a single day. A date alone means the whole
    day: its start for ``--from``, its end for ``--to``.
    """
    stripped = text.strip()
    if ":" in stripped and "T" not in stripped.upper() and " " not in stripped:
        try:
            parts = [int(p) for p in stripped.split(":")]
            tod = time(*parts)
        except (ValueError, TypeError) as exc:
            raise SargraphError(f"bad time {text!r}") from exc
        days = data["timestamp"].dt.normalize().unique() if len(data) else []
        if len(days) != 1:
            raise SargraphError(
                f"bare time {text!r} is ambiguous: data spans {len(days)} days; "
                "use an ISO datetime such as 2026-09-02T09:00"
            )
        return datetime.combine(pd.Timestamp(days[0]).date(), tod)
    try:
        value = datetime.fromisoformat(stripped)
    except ValueError as exc:
        raise SargraphError(f"bad date/time {text!r}: use ISO, e.g. 2026-09-02T09:00") from exc
    if end and len(stripped) == 10:
        return value + timedelta(days=1) - timedelta(microseconds=1)
    return value


def filter_time(loaded: Loaded, start: datetime | None, stop: datetime | None) -> Loaded:
    """Keep rows with ``start <= timestamp <= stop`` (either bound optional)."""

    def keep(frame: pd.DataFrame) -> pd.DataFrame:
        mask = pd.Series(True, index=frame.index)
        if start is not None:
            mask &= frame["timestamp"] >= start
        if stop is not None:
            mask &= frame["timestamp"] <= stop
        return frame[mask].reset_index(drop=True)

    return Loaded(data=keep(loaded.data), restarts=keep(loaded.restarts))
