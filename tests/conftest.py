"""Fixtures that are used for tests."""

from pathlib import Path

import pytest


@pytest.fixture
def test_data():
    """Returns the location of the folder where tests' data are stored."""
    return Path(__file__).parent / "data"
