"""Generic parser for text ``sar`` output (``sar -A`` and friends).

No per-section code: a header line is a timestamp followed only by non-numeric
tokens; every other timestamped line is a data row for the current header.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta

import pandas as pd

from .model import COLUMNS, DEVICE_HEADERS, RESTART_SECTION, SargraphError, section_name

log = logging.getLogger(__name__)

_BANNER = re.compile(r"^\S+\s+\S+\s+\((?P<host>[^)]+)\)\s+(?P<date>\S+)")
_TIME = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})$")
_SKIP_PREFIXES = ("Average:", "Summary:")


def _is_number(token: str) -> bool:
    try:
        float(token.replace(",", "."))
    except ValueError:
        return False
    return True


def _to_float(token: str) -> float:
    return float(token.replace(",", "."))


def _parse_date(text: str) -> date:
    """Parse the banner date: ISO, or ``mm/dd/yyyy`` (``dd/mm`` if the first part is > 12)."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return date.fromisoformat(text)
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})", text)
    if not match:
        raise SargraphError(f"unrecognised date in sar banner: {text!r}")
    first, second, year = int(match[1]), int(match[2]), int(match[3])
    if year < 100:
        year += 2000
    month, day = (second, first) if first > 12 else (first, second)
    return date(year, month, day)


def _split_time(tokens: list[str]) -> tuple[time, list[str]] | None:
    """Split a leading ``HH:MM:SS [AM|PM]`` off a line's tokens, or None if absent."""
    match = _TIME.match(tokens[0]) if tokens else None
    if not match:
        return None
    hour, minute, second = (int(g) for g in match.groups())
    rest = tokens[1:]
    if rest and rest[0] in ("AM", "PM"):
        meridiem = rest[0]
        rest = rest[1:]
        hour = hour % 12 + (12 if meridiem == "PM" else 0)
    return time(hour, minute, second), rest


class _SectionClock:  # pylint: disable=too-few-public-methods
    """Tracks the date of one section: time going backwards means midnight passed."""

    def __init__(self, start: date) -> None:
        self.day = start
        self.previous: time | None = None

    def stamp(self, tod: time) -> datetime:
        """Timestamp for a time of day, advancing the date on rollover."""
        if self.previous is not None and tod < self.previous:
            self.day += timedelta(days=1)
        self.previous = tod
        return datetime.combine(self.day, tod)


class _Parser:  # pylint: disable=too-few-public-methods
    """Line-by-line state machine behind :func:`parse_text`."""

    def __init__(self, host: str) -> None:
        self.host = host
        self.rows: list[tuple] = []
        self.base_date: date | None = None
        self.clocks: dict[str, _SectionClock] = {}
        self.header: list[str] | None = None
        self.section: str | None = None
        self.skipped = 0

    def feed(self, raw: str) -> None:
        """Consume one line."""
        line = raw.strip()
        if not line or line.startswith(_SKIP_PREFIXES):
            return
        tokens = line.split()
        banner = _BANNER.match(line)
        if banner and not _TIME.match(tokens[0]):
            self._banner(banner)
            return
        split = _split_time(tokens)
        if split is None:
            return
        tod, rest = split
        if self.base_date is None:
            raise SargraphError("no sar banner line (Linux ... (host) date) before data")
        if "LINUX RESTART" in line:
            self._restart(tod)
        elif rest and not any(_is_number(t) for t in rest):
            self._header(rest)
        else:
            self._data(tod, rest)

    def _banner(self, banner: re.Match[str]) -> None:
        self.host = banner["host"]
        self.base_date = _parse_date(banner["date"])
        self.clocks = {}
        self.header = self.section = None

    def _restart(self, tod: time) -> None:
        clock = self.clocks.get(self.section or "")
        day = clock.day if clock else self.base_date
        self.rows.append(
            (self.host, datetime.combine(day, tod), RESTART_SECTION, "", "restart", 1.0)
        )

    def _header(self, header: list[str]) -> None:
        self.header = header
        self.section = section_name(header)
        self.clocks.setdefault(self.section, _SectionClock(self.base_date))

    def _data(self, tod: time, rest: list[str]) -> None:
        if self.header is None or self.section is None:
            return
        has_device = self.header[0] in DEVICE_HEADERS or (bool(rest) and not _is_number(rest[0]))
        device, values = (rest[0], rest[1:]) if has_device else ("", rest)
        metrics = self.header[1:] if has_device else self.header
        if len(values) != len(metrics) or not all(_is_number(v) for v in values):
            self.skipped += 1
            return
        stamp = self.clocks[self.section].stamp(tod)
        self.rows.extend(
            (self.host, stamp, self.section, device, metric, _to_float(value))
            for metric, value in zip(metrics, values, strict=True)
        )


def parse_text(lines: Iterable[str], host: str = "unknown") -> pd.DataFrame:
    """Parse text sar output into the long-format table (see ``model.COLUMNS``).

    ``LINUX RESTART`` lines become rows in the ``_restart`` section.
    """
    parser = _Parser(host)
    for raw in lines:
        parser.feed(raw)
    if parser.skipped:
        log.warning("skipped %d malformed sar row(s)", parser.skipped)
    frame = pd.DataFrame(parser.rows, columns=COLUMNS)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return frame
