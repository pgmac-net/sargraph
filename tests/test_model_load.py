# pylint: disable=missing-function-docstring,missing-module-docstring
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from sargraph import load
from sargraph.model import SargraphError, Selector, select


def test_selector_parse_and_str():
    sel = Selector.parse("net.rxkB/s@eth0")
    assert (sel.section, sel.column, sel.device) == ("net", "rxkB/s", "eth0")
    assert str(sel) == "net.rxkB/s@eth0"
    assert Selector.parse("mem.%memused").device is None


@pytest.mark.parametrize("bad", ["cpu", ".x", "cpu.", "cpu.%usr@"])
def test_selector_parse_errors(bad):
    with pytest.raises(SargraphError):
        Selector.parse(bad)


def test_select_glob_columns_and_devices(sample_12h):
    data = load.load_files([sample_12h]).data
    rows = select(data, Selector.parse("cpu.%*@all"))
    assert set(rows["device"]) == {"all"}
    assert {"%usr", "%sys", "%idle"} <= set(rows["metric"])
    only_one = select(data, Selector.parse("cpu.%usr@1"))
    assert set(only_one["device"]) == {"1"}
    every = select(data, Selector.parse("cpu.%usr"))
    assert set(every["device"]) == {"all", "0", "1", "2", "3"}
    assert select(data, Selector.parse("nope.x")).empty


def test_dedup_keeps_first(sample_12h, tmp_path):
    changed = tmp_path / "second.sar"
    changed.write_text(sample_12h.read_text().replace("12.27", "99.99"))
    data = load.load_files([sample_12h, changed]).data
    cpu = data[(data["section"] == "cpu") & (data["metric"] == "%usr") & (data["device"] == "all")]
    assert 99.99 not in set(cpu["value"])
    assert 12.27 in set(cpu["value"])


def test_restarts_split_out(edge_24h):
    loaded = load.load_files([edge_24h])
    assert len(loaded.restarts) == 1
    assert "_restart" not in set(loaded.data["section"])


def test_time_filter_inclusive(sample_12h):
    loaded = load.load_files([sample_12h])
    lo = load.parse_when("00:05", loaded.data, end=False)
    hi = load.parse_when("00:15", loaded.data, end=True)
    cut = load.filter_time(loaded, lo, hi)
    stamps = set(cut.data["timestamp"])
    assert min(stamps) == datetime(2026, 9, 2, 0, 5, 1) or min(stamps) >= lo
    assert max(stamps) <= hi


def test_bare_time_ambiguous_over_two_days(edge_24h):
    loaded = load.load_files([edge_24h])
    with pytest.raises(SargraphError, match="ambiguous"):
        load.parse_when("09:00", loaded.data, end=False)


def test_iso_and_date_only_bounds():
    empty = pd.DataFrame({"timestamp": pd.to_datetime([])})
    assert load.parse_when("2026-09-02T09:30", empty, end=False) == datetime(2026, 9, 2, 9, 30)
    assert load.parse_when("2026-09-02", empty, end=False) == datetime(2026, 9, 2)
    end = load.parse_when("2026-09-02", empty, end=True)
    assert end.date() == datetime(2026, 9, 2).date() and end.hour == 23
    with pytest.raises(SargraphError):
        load.parse_when("garbage", empty, end=False)


def test_is_binary(tmp_path, sample_12h):
    assert not load.is_binary(sample_12h)
    blob = tmp_path / "sa01"
    blob.write_bytes(b"\x96\xd5\x00\x01" + b"\x00" * 64)
    assert load.is_binary(blob)


def test_binary_file_goes_through_sar(tmp_path, sample_12h, monkeypatch):
    blob = tmp_path / "sa01"
    blob.write_bytes(b"\x96\xd5\x00\x01" + b"\x00" * 64)
    calls = []

    def fake(path: Path) -> str:
        calls.append(path)
        return sample_12h.read_text()

    monkeypatch.setattr(load, "_run_sar", fake)
    data = load.load_files([blob]).data
    assert calls == [blob]
    assert "cpu" in set(data["section"])


def test_missing_file_error(tmp_path):
    with pytest.raises(SargraphError, match="no such file"):
        load.load_file(tmp_path / "absent")
