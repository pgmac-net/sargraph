"""Shared data model: the long-format table, section names and metric selectors."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass

import pandas as pd

COLUMNS = ["host", "timestamp", "section", "device", "metric", "value"]
KEY = ["host", "timestamp", "section", "device", "metric"]
RESTART_SECTION = "_restart"


class SargraphError(Exception):
    """A user-facing error: bad input, bad selector, missing tool."""


# Header signature -> short section name. Looked up by the first two header
# tokens, then by the first token alone.
SECTION_NAMES: dict[tuple[str, ...], str] = {
    ("CPU", "%usr"): "cpu",
    ("CPU", "%user"): "cpu",
    ("CPU", "total/s"): "softnet",
    ("IFACE", "rxpck/s"): "net",
    ("IFACE", "rxerr/s"): "net-err",
    ("DEV",): "disk",
    ("TTY",): "tty",
    ("proc/s",): "task",
    ("pswpin/s",): "swapping",
    ("pgpgin/s",): "paging",
    ("tps",): "io",
    ("kbmemfree",): "mem",
    ("kbswpfree",): "swap",
    ("kbhugfree",): "hugepages",
    ("dentunusd",): "inode",
    ("runq-sz",): "load",
    ("call/s",): "nfs",
    ("scall/s",): "nfsd",
    ("totsck",): "sock",
}

# Header first columns that name a device (the row's first value is the device).
DEVICE_HEADERS = frozenset(
    {"CPU", "IFACE", "DEV", "TTY", "FILESYSTEM", "MOUNTPOINT", "INTR", "BUS", "DEVICE"}
)


def section_name(header: list[str]) -> str:
    """Return the short section name for a header (the columns after the timestamp)."""
    for key in (tuple(header[:2]), tuple(header[:1])):
        if key in SECTION_NAMES:
            return SECTION_NAMES[key]
    metrics = header[1:] if header[0] in DEVICE_HEADERS else header
    first = metrics[0] if metrics else header[0]
    return "x-" + re.sub(r"[^a-z0-9-]+", "", first.lower())


@dataclass(frozen=True)
class Selector:
    """``SECTION.COLUMN[@DEVICE]``; each part may be a glob. No device means all devices."""

    section: str
    column: str
    device: str | None = None

    @classmethod
    def parse(cls, text: str) -> Selector:
        """Parse ``SECTION.COLUMN[@DEVICE]``."""
        body, _, device = text.partition("@")
        section, dot, column = body.partition(".")
        if not dot or not section or not column:
            raise SargraphError(f"bad metric {text!r}: expected SECTION.COLUMN[@DEVICE]")
        if "@" in text and not device:
            raise SargraphError(f"bad metric {text!r}: empty device after '@'")
        return cls(section, column, device or None)

    def __str__(self) -> str:
        suffix = f"@{self.device}" if self.device else ""
        return f"{self.section}.{self.column}{suffix}"

    def matches(self, section: str, metric: str, device: str) -> bool:
        """True if a (section, metric, device) triple is selected."""
        if not fnmatch.fnmatchcase(section, self.section):
            return False
        if not fnmatch.fnmatchcase(metric, self.column):
            return False
        return self.device is None or fnmatch.fnmatchcase(device, self.device)


def select(data: pd.DataFrame, selector: Selector) -> pd.DataFrame:
    """Rows of ``data`` chosen by ``selector``."""
    triples = data[["section", "metric", "device"]].drop_duplicates()
    keep = pd.Series(
        [
            selector.matches(sec, met, dev)
            for sec, met, dev in zip(
                triples["section"], triples["metric"], triples["device"], strict=True
            )
        ],
        index=triples.index,
        dtype=bool,
    )
    wanted = triples[keep]
    return data.merge(wanted, on=["section", "metric", "device"], how="inner")
