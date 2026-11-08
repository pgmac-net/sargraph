# pylint: disable=missing-function-docstring,missing-module-docstring
from datetime import datetime

import pandas as pd
import pytest

from sargraph.model import RESTART_SECTION, SargraphError, section_name
from sargraph.parse_text import parse_text


def _read(path):
    with path.open(encoding="utf-8") as handle:
        return parse_text(handle)


def test_12h_sample_sections_and_host(sample_12h):
    df = _read(sample_12h)
    assert set(df["host"]) == {"host1"}
    assert {"cpu", "mem", "load", "net", "net-err", "disk", "io", "task", "nfsd"} <= set(
        df["section"]
    )
    assert not any(s.startswith("x-") for s in df["section"])


def test_12h_midnight_is_hour_zero(sample_12h):
    df = _read(sample_12h)
    cpu = df[(df["section"] == "cpu") & (df["metric"] == "%usr") & (df["device"] == "all")]
    first = cpu["timestamp"].min()
    assert first == datetime(2026, 9, 2, 0, 5, 1)


def test_numeric_cpu_ids_are_devices(sample_12h):
    df = _read(sample_12h)
    devices = set(df[df["section"] == "cpu"]["device"])
    assert devices == {"all", "0", "1", "2", "3"}


def test_no_device_sections_have_empty_device(sample_12h):
    df = _read(sample_12h)
    assert set(df[df["section"] == "mem"]["device"]) == {""}


def test_each_section_clock_restarts_per_section(sample_12h):
    df = _read(sample_12h)
    assert df["timestamp"].dt.date.nunique() == 1


def test_24h_comma_decimals_rollover_restart_unknown(edge_24h):
    df = _read(edge_24h)
    restarts = df[df["section"] == RESTART_SECTION]
    assert list(restarts["timestamp"]) == [pd.Timestamp("2026-09-03 00:05:01")]
    cpu = df[(df["section"] == "cpu") & (df["metric"] == "%user") & (df["device"] == "all")]
    assert list(cpu["timestamp"]) == [
        pd.Timestamp("2026-09-02 23:50:01"),
        pd.Timestamp("2026-09-02 23:55:01"),
        pd.Timestamp("2026-09-03 00:00:01"),
        pd.Timestamp("2026-09-03 00:10:01"),
    ]
    assert list(cpu["value"]) == [1.5, 3.5, 5.5, 7.5]
    unknown = df[df["section"] == "x-foo-bar"]
    assert set(unknown["metric"]) == {"foo-bar", "baz"}
    assert unknown["timestamp"].max() == pd.Timestamp("2026-09-03 00:10:01")


def test_average_lines_skipped(edge_24h):
    df = _read(edge_24h)
    assert 4.25 not in set(df["value"])


def test_dd_mm_banner_date():
    lines = [
        "Linux 6.1 (h) \t25/12/2026 \t_x86_64_\t(1 CPU)",
        "",
        "10:00:01 proc/s cswch/s",
        "10:10:01 1.00 2.00",
    ]
    df = parse_text(lines)
    assert df["timestamp"].iloc[0] == pd.Timestamp("2026-12-25 10:10:01")


def test_data_without_banner_errors():
    with pytest.raises(SargraphError):
        parse_text(["10:00:01 proc/s cswch/s", "10:10:01 1 2"])


@pytest.mark.parametrize(
    ("header", "name"),
    [
        (["CPU", "%usr"], "cpu"),
        (["CPU", "total/s"], "softnet"),
        (["IFACE", "rxerr/s"], "net-err"),
        (["runq-sz", "plist-sz"], "load"),
        (["%scpu-10", "%scpu-60"], "x-scpu-10"),
    ],
)
def test_section_name(header, name):
    assert section_name(header) == name
