import logging
from contextlib import contextmanager
from functools import lru_cache

from packaging.version import Version, parse

log = logging.getLogger(__name__)


@lru_cache
def version() -> Version:
    import pandas

    return parse(pandas.__version__)


@contextmanager
def disable_copy_on_write(name):
    """Context manager to disable Pandas :ref:`pandas:copy_on_write`.

    A message is logged with level :any:`logging.DEBUG` if the setting is changed.
    """
    import pandas

    stored = pandas.options.mode.copy_on_write
    override_value = "warn" if version() >= Version("2.2.0") else False

    try:
        if stored is True:
            log.debug(f"Override pandas.mode.options.copy_on_write = True for {name}")
            pandas.options.mode.copy_on_write = override_value
        yield
    finally:
        pandas.options.mode.copy_on_write = stored


@lru_cache
def handles_parquet_attrs() -> bool:
    """Return :any:`True` if :mod:`pandas` can read/write attrs to/from Parquet files.

    If not, a message is logged.
    """
    if version() < Version("2.1.0"):
        log.info(
            f"Pandas {version()!s} < 2.1.0 cannot read/write Quantity.attrs "
            f"to/from Parquet; {__name__} will use pickle from the standard library"
        )
        return False
    else:
        return True
