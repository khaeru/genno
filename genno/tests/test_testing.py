import logging

import pytest

from genno.testing import assert_logs

log = logging.getLogger(__name__)


@pytest.mark.xfail()
def test_assert_logs(caplog):
    caplog.set_level(logging.DEBUG)

    with assert_logs(caplog, "foo"):
        log.debug("bar")
        log.info("baz")
        log.warning("spam and eggs")
