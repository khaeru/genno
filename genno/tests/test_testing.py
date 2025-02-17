import logging

import pytest

from genno import Computer, Quantity
from genno.testing import (
    assert_logs,
    assert_qty_allclose,
    assert_qty_equal,
    assert_units,
)

log = logging.getLogger(__name__)


@pytest.mark.xfail()
def test_assert_logs(caplog) -> None:
    caplog.set_level(logging.DEBUG)

    with assert_logs(caplog, "foo"):
        log.debug("bar")
        log.info("baz")
        log.warning("spam and eggs")


def test_assert_units() -> None:
    assert_units(Quantity(), "")


def test_assert_check_type() -> None:
    """Mismatched types in :func:`assert_qty_equal` and :func:`assert_qty_allclose`."""
    with pytest.raises(AssertionError):
        assert_qty_equal(int(1), 2.2)

    with pytest.raises(AssertionError):
        assert_qty_allclose(int(1), 2.2)


def test_deprecated_import() -> None:
    with pytest.warns(DeprecationWarning, match="random_qty"):
        from genno.testing import random_qty  # noqa:F401


@pytest.mark.xfail(raises=TypeError)
def test_runtest_makereport() -> None:
    """The Pytest hook :func:`.pytest_runtest_makereport` works."""
    c = Computer()

    def func(x):
        return "a" + x

    c.add("test", func, 1.0)

    # This line raises a ComputationError, but the
    # genno.testing.pytest_runtest_makereport hook implementation unwraps the TypeError
    # that triggers it; this then satisfies the xfail marker on the test function.
    c.get("test")
