"""Test configuration."""
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_data_path():
    """Path to the directory containing test data."""
    return Path(__file__).parent / "data"
