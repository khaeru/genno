import contextlib
import logging
from functools import partial
from itertools import chain, zip_longest
from typing import Dict

import numpy as np
import pandas as pd
import pint
import pytest
import xarray as xr
from dask.core import quote
from pandas.testing import assert_series_equal

from genno import Computer, Key, Quantity

log = logging.getLogger(__name__)


def add_large_data(c: Computer, num_params, N_dims=6):
    """Add nodes to `c` that return large-ish data.

    The result is a matrix wherein the Cartesian product of all the keys is very large—
    about 2e17 elements for N_dim = 6—but the contents are very sparse. This can be
    handled by :class:`.SparseDataArray`, but not by :class:`xarray.DataArray` backed
    by :class:`np.array`.
    """
    # Dimensions and their lengths (Fibonacci numbers)
    dims = "abcdefg"[:N_dims]
    sizes = [233, 377, 610, 987, 1597, 2584, 4181][:N_dims]

    # commented; for debugging
    # # Output something like "True: 2584 values / 2.182437e+17 = 1.184e-12% full"
    # from math import prod
    #
    # total = prod(sizes)
    # log.info(
    #     # See https://github.com/pydata/sparse/issues/429; total elements must be
    #     # less than the maximum value of np.intp
    #     repr(total < np.iinfo(np.intp).max)
    #     + f": {max(sizes)} values / {total:3e} = {100 * max(sizes) / total:.3e}% full"
    # )

    # Names like f_0000 ... f_1596 along each dimension
    coords = []
    for d, N in zip(dims, sizes):
        coords.append([f"{d}_{i:04d}" for i in range(N)])
        # Add to Computer
        c.add(d, quote(coords[-1]))

    def get_large_quantity(name):
        """Make a DataFrame containing each label in *coords* ≥ 1 time."""
        values = list(zip_longest(*coords, np.random.rand(max(sizes))))
        log.info(f"{len(values)} values")
        return Quantity(
            pd.DataFrame(values, columns=list(dims) + ["value"])
            .ffill()
            .set_index(list(dims)),
            units=pint.get_application_registry().kilogram,
            name=name,
        )

    # Fill the Scenario with quantities named q_01 ... q_09
    keys = []
    for i in range(num_params):
        key = Key(f"q_{i:02d}", dims)
        c.add(key, (partial(get_large_quantity, key),))
        keys.append(key)

    return keys


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
    x = Quantity(
        xr.DataArray(np.random.rand(len(t), len(y)), coords=[("t", t), ("y", y)]),
        units=ureg.kg,
    )

    # As a pd.DataFrame with units
    x_df = x.to_series().rename("value").reset_index()
    x_df["unit"] = "kg"

    scen.init_par("x", ["t", "y"])
    scen.add_par("x", x_df)

    return t, t_foo, t_bar, x


def add_test_data2(c: Computer):
    """:func:`add_test_data` operating on a Computer, not an ixmp.Scenario."""
    # TODO combine with add_dantzig(), below
    # New sets
    t_foo = ["foo{}".format(i) for i in (1, 2, 3)]
    t_bar = ["bar{}".format(i) for i in (4, 5, 6)]
    t = t_foo + t_bar
    y = list(map(str, range(2000, 2051, 10)))

    # Add to Computer
    c.add("t", quote(t))
    c.add("y", quote(y))

    # Data
    ureg = pint.get_application_registry()
    x = Quantity(
        xr.DataArray(np.random.rand(len(t), len(y)), coords=[("t", t), ("y", y)]),
        units=ureg.kg,
    )

    # Add, including sums and to index
    c.add(Key("x", ("t", "y")), Quantity(x), index=True, sums=True)

    return t, t_foo, t_bar, x


_i = ["seattle", "san-diego"]
_j = ["new-york", "chicago", "topeka"]
_TEST_DATA = {
    Key.from_str_or_key(k): data
    for k, data in {
        "a:i": (xr.DataArray([350, 600], coords=[("i", _i)]), "cases"),
        "b:j": (xr.DataArray([325, 300, 275], coords=[("i", _j)]), "cases"),
        "d:i-j": (
            xr.DataArray(
                [[2.5, 1.7, 1.8], [2.5, 1.8, 1.4]], coords=[("i", _i), ("j", _j)]
            ),
            "km",
        ),
        "f:": (90.0, "USD/km"),
        # TODO complete the following
        # Decision variables and equations
        "x:i-j": (
            xr.DataArray([[0, 0, 0], [0, 0, 0]], coords=[("i", _i), ("j", _j)]),
            "cases",
        ),
        "z:": (0, "cases"),
        "cost:": (0, "USD"),
        "cost-margin:": (0, "USD"),
        "demand:j": (xr.DataArray([0, 0, 0], coords=[("j", _j)]), "cases"),
        "demand-margin:j": (xr.DataArray([0, 0, 0], coords=[("j", _j)]), "cases"),
        "supply:i": (xr.DataArray([0, 0], coords=[("i", _i)]), "cases"),
        "supply-margin:i": (xr.DataArray([0, 0], coords=[("i", _i)]), "cases"),
    }.items()
}


def get_test_quantity(key):
    """Computation that returns test data."""
    value, unit = _TEST_DATA[key]
    return Quantity(value, name=key.name, units=unit)


def add_dantzig(c: Computer):
    """Add contents analogous to the ixmp Dantzig scenario."""

    c.add("i", quote(_i))
    c.add("j", quote(_j))

    _all = list()
    for key in _TEST_DATA.keys():
        c.add(key, (partial(get_test_quantity, key),), index=True, sums=True)
        _all.append(key)

    c.add("all", sorted(_all))


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
    """Fixture to run tests twice, for both Quantity implementations."""
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
