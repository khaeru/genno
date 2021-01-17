import contextlib
from itertools import chain
from typing import Dict

import numpy as np
import pint
import pytest
import xarray as xr
from pandas.testing import assert_series_equal

from .core.quantity import Quantity


def add_test_data(scen):
    # New sets
    t_foo = ["foo{}".format(i) for i in (1, 2, 3)]
    t_bar = ["bar{}".format(i) for i in (4, 5, 6)]
    t = t_foo + t_bar
    y = list(map(str, range(2000, 2051, 10)))

    # Add to scenario
    scen.init_set("t")
    scen.add_set("t", t)
    scen.init_set("y")
    scen.add_set("y", y)

    # Data
    ureg = pint.get_application_registry()
    x = xr.DataArray(
        np.random.rand(len(t), len(y)),
        coords=[t, y],
        dims=["t", "y"],
        attrs={"_unit": ureg.Unit("kg")},
    )
    x = Quantity(x)

    # As a pd.DataFrame with units
    x_df = x.to_series().rename("value").reset_index()
    x_df["unit"] = "kg"

    scen.init_par("x", ["t", "y"])
    scen.add_par("x", x_df)

    return t, t_foo, t_bar, x


@contextlib.contextmanager
def assert_logs(caplog, message_or_messages=None, at_level=None):
    """Assert that *message_or_messages* appear in logs.

    Use assert_logs as a context manager for a statement that is expected to trigger
    certain log messages. assert_logs checks that these messages are generated.

    Derived from :func:`ixmp.testing.assert_logs`.

    Example
    -------

    def test_foo(caplog):
        with assert_logs(caplog, 'a message'):
            logging.getLogger(__name__).info('this is a message!')

    Parameters
    ----------
    caplog : object
        The pytest caplog fixture.
    message_or_messages : str or list of str
        String(s) that must appear in log messages.
    at_level : int, optional
        Messages must appear on 'genno' or a sub-logger with at least this level.
    """
    # Wrap a string in a list
    expected = (
        [message_or_messages]
        if isinstance(message_or_messages, str)
        else message_or_messages
    )

    # Record the number of records prior to the managed block
    first = len(caplog.records)

    if at_level is not None:
        # Use the pytest caplog fixture's built-in context manager to temporarily set
        # the level of the logger for the whole package (parent of the current module)
        ctx = caplog.at_level(at_level, logger=__name__.split(".")[0])
    else:
        # Python 3.6 compatibility: use suppress for nullcontext
        nullcontext = getattr(contextlib, "nullcontext", contextlib.suppress)
        # ctx does nothing
        ctx = nullcontext()

    try:
        with ctx:
            yield  # Nothing provided to the managed block
    finally:
        # List of bool indicating whether each of `expected` was found
        found = [any(e in msg for msg in caplog.messages[first:]) for e in expected]

        if not all(found):
            # Format a description of the missing messages
            lines = chain(
                ["Did not log:"],
                [f"    {repr(msg)}" for i, msg in enumerate(expected) if not found[i]],
                ["among:"],
                ["    []"]
                if len(caplog.records) == first
                else [f"    {repr(msg)}" for msg in caplog.messages[first:]],
            )
            pytest.fail("\n".join(lines))


def assert_qty_equal(a, b, check_type=True, check_attrs=True, **kwargs):
    """Assert that Quantity objects *a* and *b* are equal.

    When Quantity is AttrSeries, *a* and *b* are first passed through
    :meth:`as_quantity`.
    """
    if not check_type:
        a = Quantity(a)
        b = Quantity(b)

    if Quantity.CLASS == "AttrSeries":
        try:
            a = a.sort_index()
            b = b.sort_index()
        except TypeError:
            pass
        assert_series_equal(a, b, check_dtype=False, **kwargs)
    else:
        import xarray.testing

        xarray.testing.assert_equal(a, b, **kwargs)

    # Check attributes are equal
    if check_attrs:
        assert a.attrs == b.attrs


def assert_qty_allclose(a, b, check_type=True, check_attrs=True, **kwargs):
    """Assert that Quantity objects *a* and *b* have numerically close values.

    When Quantity is AttrSeries, *a* and *b* are first passed through
    :meth:`as_quantity`.
    """
    if not check_type:
        a = Quantity(a)
        b = Quantity(b)

    if Quantity.CLASS == "AttrSeries":
        assert_series_equal(a.sort_index(), b.sort_index(), **kwargs)
    else:
        import xarray.testing

        kwargs.pop("check_dtype", None)
        xarray.testing.assert_allclose(a._sda.dense, b._sda.dense, **kwargs)

    # check attributes are equal
    if check_attrs:
        assert a.attrs == b.attrs


@pytest.fixture(params=["AttrSeries", "SparseDataArray"])
def parametrize_quantity_class(request):
    """Fixture to run tests twice, for both reporting Quantity classes."""
    pre = Quantity.CLASS

    Quantity.CLASS = request.param
    yield

    Quantity.CLASS = pre


def random_qty(shape: Dict[str, int], **kwargs):
    """Return a Quantity with *shape* and random contents.

    Parameters
    ----------
    shape : dict
        Mapping from dimension names to
    kwargs
        Other keyword arguments to :class:`Quantity`.

    Returns
    -------
    Quantity
        Keys in `shape`—e.g. "foo"—result in a dimension named "foo" with
        coords "foo0", "foo1", etc., with total length matching the value.
        Data is random.
    """
    return Quantity(
        xr.DataArray(
            np.random.rand(*shape.values()),
            coords={
                dim: [f"{dim}{i}" for i in range(length)]
                for dim, length in shape.items()
            },
            dims=shape.keys(),
        ),
        **kwargs,
    )
