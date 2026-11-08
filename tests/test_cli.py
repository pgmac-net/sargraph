# pylint: disable=missing-function-docstring,missing-module-docstring
import pytest
from typer.testing import CliRunner

from sargraph.cli import app

runner = CliRunner()
MAGIC = {"png": b"\x89PNG", "jpg": b"\xff\xd8\xff", "svg": b"<?xml"}


def _graph(sample, *extra):
    return runner.invoke(app, ["graph", str(sample), *extra])


def test_exports_all_three_formats(sample_12h, tmp_path):
    outs = [tmp_path / f"o.{ext}" for ext in ("png", "svg", "jpg")]
    args = ["-m", "cpu.%usr@all", "-m", "mem.%memused"]
    for out in outs:
        args += ["-o", str(out)]
    result = _graph(sample_12h, *args)
    assert result.exit_code == 0, result.output
    for out in outs:
        assert out.read_bytes().startswith(MAGIC[out.suffix[1:]]), out


def test_jpeg_extension_alias(sample_12h, tmp_path):
    out = tmp_path / "o.jpeg"
    assert _graph(sample_12h, "-m", "cpu.%usr@all", "-o", str(out)).exit_code == 0
    assert out.read_bytes().startswith(MAGIC["jpg"])


@pytest.mark.parametrize("layout", ["stacked", "combined"])
def test_layouts_single_file(sample_12h, tmp_path, layout):
    out = tmp_path / "o.png"
    result = _graph(
        sample_12h, "-m", "cpu.%usr@all", "-m", "cpu.%sys@all", "--layout", layout, "-o", str(out)
    )
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_separate_layout_pattern(sample_12h, tmp_path):
    result = _graph(
        sample_12h,
        "-m",
        "cpu.%usr@all",
        "-m",
        "mem.%memused",
        "--layout",
        "separate",
        "-o",
        str(tmp_path / "g-{n}.png"),
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "g-1.png").exists() and (tmp_path / "g-2.png").exists()


def test_separate_needs_placeholder(sample_12h, tmp_path):
    result = _graph(
        sample_12h,
        "-m",
        "cpu.%usr@all",
        "-m",
        "mem.%memused",
        "--layout",
        "separate",
        "-o",
        str(tmp_path / "g.png"),
    )
    assert result.exit_code == 2
    assert "{n}" in result.output


def test_time_range_and_empty_selection(sample_12h, tmp_path):
    out = tmp_path / "o.png"
    ok = _graph(
        sample_12h, "-m", "cpu.%usr@all", "--from", "00:00", "--to", "00:20", "-o", str(out)
    )
    assert ok.exit_code == 0, ok.output
    empty = _graph(sample_12h, "-m", "cpu.%usr@all", "--from", "20:00", "-o", str(out))
    assert empty.exit_code == 2
    assert "no data matches" in empty.output


def test_stdout_needs_format(sample_12h):
    result = _graph(sample_12h, "-m", "cpu.%usr@all", "-o", "-")
    assert result.exit_code == 2
    assert "--format" in result.output


def test_stdout_png(sample_12h):
    result = _graph(sample_12h, "-m", "cpu.%usr@all", "-o", "-", "--format", "png")
    assert result.exit_code == 0
    assert result.stdout_bytes.startswith(MAGIC["png"])


def test_bad_extension_and_no_output(sample_12h, tmp_path):
    bad = _graph(sample_12h, "-m", "cpu.%usr@all", "-o", str(tmp_path / "o.gif"))
    assert bad.exit_code == 2
    none = _graph(sample_12h, "-m", "cpu.%usr@all")
    assert none.exit_code != 0


def test_multi_host_labels(sample_12h, tmp_path):
    other = tmp_path / "other.sar"
    other.write_text(sample_12h.read_text().replace("(host1)", "(host2)"))
    out = tmp_path / "o.svg"
    result = runner.invoke(
        app, ["graph", str(sample_12h), str(other), "-m", "cpu.%usr@all", "-o", str(out)]
    )
    assert result.exit_code == 0, result.output
    text = out.read_text()
    assert "host1:%usr@all" in text and "host2:%usr@all" in text


def test_list(sample_12h):
    result = runner.invoke(app, ["list", str(sample_12h)])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert "cpu.%usr@all" in lines
    assert "mem.%memused" in lines
