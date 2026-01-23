import logging
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache

from packaging.version import Version, parse

__all__ = [
    "disable_copy_on_write",
    "handles_parquet_attrs",
    "manager_classes",
    "version",
]

log = logging.getLogger(__name__)


@cache
def version() -> Version:
    """Return the version of :mod:`pandas` as a :class:`packaging.version.Version`."""
    import pandas

    return parse(pandas.__version__)


@contextmanager
def disable_copy_on_write(name: str) -> Iterator[None]:
    """Context manager to disable Pandas :ref:`pandas:copy_on_write`.

    A message is logged with level :any:`logging.DEBUG` if the setting is changed. The
    fixture has no effect in pandas 3.0.0 and later, in which the option is always
    enabled.
    """
    import pandas

    cow = "mode.copy_on_write"

    was_enabled = version() < Version("3") and pandas.get_option(cow)
    if was_enabled:
        log.debug(f"Override pandas.options.{cow} = True for {name}")
        pandas.set_option(cow, False if Version("2.2") <= version() else "warn")

    try:
        yield
    finally:
        if was_enabled:
            pandas.set_option(cow, True)


@cache
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


@cache
def manager_classes() -> tuple[type, ...]:
    """Pandas class(es) for which a fast-path :py:`pd.Series.__init__()` can be used."""
    if version() < Version("3"):
        from pandas.core.internals.base import DataManager

        return (DataManager,)
    else:
        from pandas.core.internals.managers import SingleBlockManager

        return (SingleBlockManager,)
