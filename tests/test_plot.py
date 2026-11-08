# pylint: disable=missing-function-docstring,missing-module-docstring
import numpy as np

from sargraph import load, plot
from sargraph.model import Selector, select


def _lines(edge_24h, restarts):
    loaded = load.load_files([edge_24h])
    rows = select(loaded.data, Selector.parse("cpu.%user@all"))
    group = plot.Group(Selector.parse("cpu.%user@all"), rows)
    figs = plot.render([group], restarts, plot.Options())
    return figs[0][1].axes[0].lines


def test_restart_breaks_the_line(edge_24h):
    loaded = load.load_files([edge_24h])
    (line,) = _lines(edge_24h, loaded.restarts)
    ydata = np.asarray(line.get_ydata(), dtype=float)
    assert np.isnan(ydata).sum() == 1
    assert len(ydata) == 5  # 4 samples + 1 gap


def test_no_restarts_no_gap(edge_24h):
    loaded = load.load_files([edge_24h])
    (line,) = _lines(edge_24h, loaded.restarts.iloc[0:0])
    assert not np.isnan(np.asarray(line.get_ydata(), dtype=float)).any()
