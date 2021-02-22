import logging
import re

import pytest

from genno import Computer, Key, configure
from genno.compat.pyam import HAS_PYAM
from genno.config import HANDLERS, handles

# NB ixmp is currently used in the genno test suite: ixmp.testing.run_notebook is
#    imported by test_exceptions.py. This in turn cases ixmp to register its own
#    handlers: 2 new, and 1 overriding the built-in one for "units:".
THIRD_PARTY_HANDLERS = 2


def test_handlers():
    # Expected config handlers are available
    assert 8 + (1 * HAS_PYAM) + THIRD_PARTY_HANDLERS == len(HANDLERS)

    # Handlers are all callable
    for key, func in HANDLERS.items():
        assert isinstance(key, str) and callable(func)


@pytest.mark.parametrize(
    "name",
    [
        "config-aggregate.yaml",
        "config-combine.yaml",
        "config-general0.yaml",
        pytest.param(
            "config-general1.yaml", marks=pytest.mark.xfail(raises=ValueError)
        ),
        "config-report.yaml",
        "config-units.yaml",
    ],
)
def test_file(test_data_path, name):
    """Test handling configuration file syntax using test data files."""
    c = Computer()

    # Set up test contents
    c.add(Key("X", list("abc")), None, index=True, sums=True)
    c.add(Key("Y", list("bcd")), None, index=True, sums=True)

    c.configure(path=test_data_path / name)


def test_global(test_data_path):
    configure(path=test_data_path / "config-units.yaml")

    with pytest.raises(
        RuntimeError, match="Cannot apply non-global configuration without a Computer"
    ):
        configure(path=test_data_path / "config-global.yaml")


def test_handles(caplog):
    """:func:`handles` raises a warning when used twice."""
    caplog.set_level(logging.DEBUG)

    @handles("foo")
    def foo1(c: Computer, info):
        """Test function; never executed."""

    assert len(caplog.messages) == 0

    @handles("foo")
    def foo2(c: Computer, info):
        """Test function; never executed."""

    assert 1 == len(caplog.messages)
    assert re.match(
        "Override handler <function test_handles.<locals>.foo1 [^>]*> for  'foo:'",
        caplog.messages[0],
    )
