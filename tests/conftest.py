# pylint: disable=missing-function-docstring,missing-module-docstring
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"


@pytest.fixture(name="sample_12h")
def fixture_sample_12h() -> Path:
    return DATA / "sample_12h.sar"


@pytest.fixture(name="edge_24h")
def fixture_edge_24h() -> Path:
    return DATA / "edge_24h.sar"
