import logging

import pytest

from genno.testing import assert_logs, assert_qty_allclose, assert_qty_equal

log = logging.getLogger(__name__)


@pytest.mark.xfail()
def test_assert_logs(caplog):
    caplog.set_level(logging.DEBUG)

    with assert_logs(caplog, "foo"):
        log.debug("bar")
        log.info("baz")
        log.warning("spam and eggs")


def test_assert_check_type():
    """Mismatched types in :func:`assert_qty_equal` and :func:`assert_qty_allclose`."""
    with pytest.raises(AssertionError):
        assert_qty_equal(int(1), 2.2)

    with pytest.raises(AssertionError):
        assert_qty_allclose(int(1), 2.2)
