"""Test configuration."""
from pathlib import Path

import pint
import pytest


@pytest.fixture(scope="session")
def test_data_path():
    """Path to the directory containing test data."""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def ureg():
    """Application-wide units registry."""
    registry = pint.get_application_registry()

    # Used by .compat.ixmp, .compat.pyam
    registry.define("USD = [USD]")
    registry.define("case = [case]")

    yield registry
