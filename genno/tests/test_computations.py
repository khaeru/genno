import logging
import random
import re
from contextlib import nullcontext
from functools import partial
from typing import Hashable, Iterable, Mapping

import numpy as np
import pandas as pd
import pint
import pytest
import xarray as xr
from dask.core import quote
from numpy.testing import assert_allclose
from pandas.testing import assert_series_equal

from genno import Computer, Quantity, computations
from genno.core.sparsedataarray import SparseDataArray
from genno.testing import (
    add_large_data,
    add_test_data,
    assert_logs,
    assert_qty_allclose,
    assert_qty_equal,
    random_qty,
)

pytestmark = pytest.mark.usefixtures("parametrize_quantity_class")


@pytest.fixture(scope="function")
def data():
    """Yields a computer, then the values of :func:`.add_test_data`."""
    c = Computer()
    yield [c] + list(add_test_data(c))


@pytest.mark.parametrize(
    "operands, size",
    [
        (("a", "a"), 18),
        (("a", "x"), 36),
        (("x", "b"), 36),
        (("a", "b"), 36),
        (("a", "x", "b"), 36),
    ],
)
def test_add(data, operands, size):
    # Unpack
    c, t, t_foo, t_bar, x = data

    y = c.get("y")
    x = c.get("x:t-y")
    a = Quantity(
        xr.DataArray(
            np.random.rand(len(t_foo), len(y)), coords=[t_foo, y], dims=["t", "y"]
        ),
        units=x.units,
    )
    b = Quantity(
        xr.DataArray(
            np.random.rand(len(t_bar), len(y)), coords=[t_bar, y], dims=["t", "y"]
        ),
        units=x.units,
    )

    c.add("a:t-y", a)
    c.add("b:t-y", b)

    key = c.add(
        "result", tuple([computations.add] + [f"{name}:t-y" for name in operands])
    )

    result = c.get(key)
    assert size == result.size, result.to_series()


def test_add_units():
    """Units are handled correctly by :func:`.add`."""
    A = Quantity(1.0, units="kg")
    B = Quantity(1.0, units="tonne")

    # Units of result are units of the first argument
    assert_qty_equal(Quantity(1001.0, units="kg"), computations.add(A, B))
    assert_qty_equal(Quantity(1.001, units="tonne"), computations.add(B, A))

    with pytest.raises(ValueError, match="Units 'kg' and 'km' are incompatible"):
        computations.add(A, Quantity(1.0, units="km"))


@pytest.mark.parametrize("keep", (True, False))
def test_aggregate0(caplog, data, keep):
    *_, t_foo, t_bar, x = data

    t_groups = dict(foo=t_foo, bar=t_bar)

    result = computations.aggregate(x, dict(t=t_groups), keep)
    assert result.name == x.name and result.units == x.units  # Pass through

    # Result has the expected dimensions
    assert set(t_groups) | (set(t_foo + t_bar) if keep else set()) == set(
        result.coords["t"].data
    )

    # Now with a group ID that duplicates one of the existing index names
    t_groups[t_foo[0]] = t_foo[:1]
    with (
        assert_logs(
            caplog, f"t='{t_foo[0]}' is already present in quantity 'Quantity X'"
        )
        if keep
        else nullcontext()
    ):
        result = computations.aggregate(x, dict(t=t_groups), keep)

    # Two dimensions
    result = computations.aggregate(x, {"t": t_groups, "y": {"2k": [2000, 2010]}}, keep)
    assert "2k" in result.coords["y"]


@pytest.mark.parametrize("keep", (True, False))
def test_aggregate_regex(caplog, data, keep):
    """:func:`aggregate` using regular expressions."""
    *_, t_foo, t_bar, x = data

    # Aggregate using regular expressions
    t_groups = dict(foo=[re.compile("foo[123]")], bar=[re.compile("b[ar]{2}.")])

    # Operation completes
    result = computations.aggregate(x, dict(t=t_groups), keep)

    # Name and units pass through
    assert result.name == x.name and result.units == x.units

    # Result has the expected dimensions
    assert set(t_groups) | (set(t_foo + t_bar) if keep else set()) == set(
        result.coords["t"].data
    )


def test_apply_units(data, caplog):
    # Unpack
    *_, x = data

    registry = pint.get_application_registry()

    # Brute-force replacement with incompatible units
    with assert_logs(
        caplog, "Replace 'kilogram' with incompatible 'liter'", at_level=logging.DEBUG
    ):
        result = computations.apply_units(x, "litres")
    assert result.units == registry.Unit("litre")
    # No change in values
    assert_series_equal(result.to_series(), x.to_series())
    assert result.name == x.name  # Pass through

    # Compatible units: magnitudes are also converted
    with assert_logs(
        caplog, "Convert 'kilogram' to 'metric_ton'", at_level=logging.DEBUG
    ):
        result = computations.apply_units(x, "tonne")
    assert result.units == registry.Unit("tonne")
    assert_series_equal(result.to_series(), x.to_series() * 0.001)

    # Remove unit
    x.units = registry.Unit("dimensionless")

    caplog.clear()
    result = computations.apply_units(x, "kg")
    # Nothing logged when _unit attr is missing
    assert len(caplog.messages) == 0
    assert result.units == registry.Unit("kg")
    assert_series_equal(result.to_series(), x.to_series())


def test_assign_units(data, caplog):
    # Unpack
    *_, x = data

    registry = pint.get_application_registry()

    # Brute-force replacement with incompatible units
    with assert_logs(
        caplog,
        "Replace 'kilogram' with 'liter' with different dimensionality",
        at_level=logging.INFO,
    ):
        result = computations.assign_units(x, "litres")
    assert result.units == registry.Unit("litre")
    # No change in values
    assert_series_equal(result.to_series(), x.to_series())
    assert result.name == x.name  # Pass through

    # Compatible units: magnitudes are not changed
    with assert_logs(
        caplog,
        "Replace 'kilogram' with 'metric_ton' without altering magnitudes",
        at_level=logging.INFO,
    ):
        result = computations.assign_units(x, "tonne")
    assert result.units == registry.Unit("tonne")
    assert_series_equal(result.to_series(), x.to_series())

    # Remove unit
    x.units = registry.Unit("dimensionless")

    caplog.clear()
    result = computations.assign_units(x, "kg")
    # Nothing logged when _unit attr is missing
    assert len(caplog.messages) == 0
    assert result.units == registry.Unit("kg")
    assert_series_equal(result.to_series(), x.to_series())


def test_convert_units(data, caplog):
    # Unpack
    *_, x = data

    registry = pint.get_application_registry()

    # Brute-force replacement with incompatible units
    with pytest.raises(ValueError, match="cannot be converted to"):
        result = computations.convert_units(x, "litres")

    # Compatible units: magnitudes are also converted
    result = computations.convert_units(x, "tonne")
    assert registry.Unit("tonne") == result.units
    assert_series_equal(
        result.to_series(), (x.to_series() * 0.001).rename("Quantity X")
    )
    assert result.name == x.name  # Pass through

    # Remove unit
    x.units = registry.Unit("dimensionless")

    with pytest.raises(ValueError, match="cannot be converted to"):
        result = computations.convert_units(x, "kg")


@pytest.mark.parametrize(
    "map_values, kwarg",
    (
        ([[1.0, 1, 0], [0, 0, 1]], dict()),
        pytest.param(
            [[1.0, 1, 0], [0, 1, 1]],
            dict(strict=True),
            marks=pytest.mark.xfail(raises=ValueError, reason="invalid map"),
        ),
    ),
)
def test_broadcast_map(ureg, map_values, kwarg):
    x = ["x1"]
    y = ["y1", "y2"]
    z = ["z1", "z2", "z3"]
    q = Quantity(xr.DataArray([[42.0, 43]], coords=[("x", x), ("y", y)]))
    m = Quantity(xr.DataArray(map_values, coords=[("y", y), ("z", z)]))

    result = computations.broadcast_map(q, m, **kwarg)
    exp = Quantity(
        xr.DataArray([[42.0, 42, 43]], coords=[("x", x), ("z", z)]),
        units=ureg.dimensionless,
    )

    assert_qty_equal(exp, result)


def test_combine(ureg, data):
    *_, t_bar, x = data

    # Without select, preserves the "t" dimension
    result = computations.combine(x, x, x, weights=(-1, 0.2, 0.8))

    assert ("t", "y") == result.dims
    assert 36 == result.size
    assert all(1e-15 > result.to_series().values)

    # With select, the selected values are summed along the "t" dimension
    result = computations.combine(
        x, x, select=(dict(t=t_bar), dict(t=t_bar)), weights=(-1, 1)
    )

    assert ("y",) == result.dims
    assert 6 == result.size
    assert all(1e-15 > result.to_series().values)

    # Incompatible units raises ValueError
    x2 = Quantity(x, units=ureg.metre)
    with pytest.raises(
        ValueError, match=re.escape("Cannot combine() units kilogram and meter")
    ):
        computations.combine(
            x, x2, select=(dict(t=t_bar), dict(t=t_bar)), weights=(-1, 1)
        )


def test_concat(ureg, data):
    *_, t_foo, t_bar, x = data

    # Split x into two concatenateable quantities
    a = computations.select(x, dict(t=t_foo))
    b = computations.select(x, dict(t=t_bar))

    # Concatenate
    computations.concat(a, b, dim="t")

    # Concatenate twice on a new dimension
    result = computations.concat(x, x, dim=pd.Index(["z1", "z2"], name="z"))

    # NB for AttrSeries, the new dimension is first; for SparseDataArray, last
    assert {"t", "y", "z"} == set(result.dims)
    assert ureg.Unit("kg") == x.units == result.units


def test_concat_dim_order(data):
    """:func:`.concat` succeeds even if dimension are not in matching order on operands.

    Test of https://github.com/khaeru/genno/issues/38.
    """
    *_, x = data

    # Create another Quantity like `x`, but with dims in the opposite order
    z = Quantity(
        x.to_series()
        .reset_index()
        .eval("y = y + 1000")
        .set_index(list(reversed(x.dims)))
        .iloc[:, 0]
    )
    assert tuple(reversed(x.dims)) == z.dims

    # Concatenation succeeds
    result = computations.concat(x, z)

    # Dims and length are as expected
    assert set(x.dims) == set(z.dims) == set(result.dims)
    assert len(x) + len(z) == len(result)

    # Dimensions were aligned correctly such that "y" in the result contains labels from
    # the same dimension in both operands
    assert set(x.coords["y"].data) | set(z.coords["y"].data) == set(
        result.coords["y"].data
    )


@pytest.mark.parametrize("func", [computations.div, computations.ratio])
def test_div(func, ureg):
    # Non-overlapping dimensions can be broadcast together
    A = random_qty(dict(x=3, y=4), units="km")
    B = random_qty(dict(z=2), units="hour")

    result = func(A, B)
    assert ("x", "y", "z") == result.dims
    assert ureg.Unit("km / hour") == result.units


def test_div_scalar(data, ureg):
    """:func:`.div` handles scalar numerator."""

    *_, x = data

    result = computations.div(2.0, x)
    assert ("t", "y") == result.dims
    assert_qty_equal(
        2.0 / x.sel(t="foo1", y=2000), result.sel(t="foo1", y=2000), check_attrs=False
    )


def test_drop_vars(data):
    # Unpack
    *_, x = data

    result = computations.drop_vars(x, "t")
    assert result.name == x.name and result.units == x.units  # Pass through
    assert set(x.dims) == {"t"} | set(result.dims)


def test_group_sum(ureg):
    a = "a1 a2".split()
    b = "b1 b2 b3".split()
    X = Quantity(
        xr.DataArray(np.random.rand(2, 3), coords=[("a", a), ("b", b)]),
        units=ureg.kg,
        name="Foo",
    )

    result = computations.group_sum(X, "a", "b")
    assert result.name == X.name and result.units == X.units  # Pass through
    assert ("a",) == result.dims
    assert 2 == len(result)


def test_index_to(ureg):
    q = random_qty(dict(x=3, y=5))
    q.name = "Foo"
    q.units = ureg.kg

    exp = q / q.sel(x="x0")
    exp.units = ""  # Indexed values are dimensionless

    # Called with a mapping
    result = computations.index_to(q, dict(x="x0"))
    assert_qty_equal(exp, result)
    assert exp.name == result.name

    # Called with two positional arguments
    result = computations.index_to(q, "x", "x0")
    assert_qty_equal(exp, result)

    # Default first index selected if 'None' is given
    result = computations.index_to(q, "x")
    assert_qty_equal(exp, result)

    result = computations.index_to(q, dict(x=None))
    assert_qty_equal(exp, result)

    # Invalid calls
    with pytest.raises(TypeError, match="expected a mapping from 1 key to 1 value"):
        computations.index_to(q, dict(x="x0", y="y0"))  # Length != 1

    with pytest.raises(KeyError):
        computations.index_to(q, dict(x="x99"))  # Mapping to something invalid


@pytest.mark.parametrize(
    "shape",
    [
        dict(x=3),
        dict(x=3, y=3),
        dict(y=3, x=3),
        dict(x=3, y=3, z=2),
        dict(y=3, x=3, z=2),
        dict(y=3, z=2, x=3),
    ],
)
def test_interpolate(caplog, ureg, shape):
    """Test :func:`.interpolate`."""
    # Generate a random quantity with one dimension indexed by integers
    q = random_qty(shape, name="Foo", units=ureg.kg)
    x = [2020, 2030, 2040]
    q = q.assign_coords({"x": x})

    # Linear interpolation of 1 point
    result = computations.interpolate(q, dict(x=2025), assume_sorted=False)
    assert result.name == q.name and result.units == q.units  # Pass through
    assert "interpolate(…, assume_sorted=False) ignored" in caplog.messages

    # Result has the expected class, dimensions, and values
    assert isinstance(result, q.__class__)
    assert tuple([d for d in q.dims if d != "x"]) == result.dims
    assert_qty_allclose(
        result, 0.5 * q.sel(x=[2020, 2030]).sum("x"), ignore_extra_coords=True
    )

    # Extrapolation on both ends of the data
    x = sorted(x + [x[0] - 1, x[-1] + 1])

    # interpolate() works
    result = computations.interpolate(
        q, dict(x=x), method="linear", kwargs=dict(fill_value="extrapolate")
    )

    # Produces the expected results
    r = result
    for i1, i2, i3 in ((0, 1, 2), (-1, -2, -3)):
        # Slope interior to the existing data
        slope_int = (r.sel(x=x[i3], drop=True) - r.sel(x=x[i2], drop=True)) / (
            x[i3] - x[i2]
        )
        # Slope to extrapolated points
        slope_ext = (r.sel(x=x[i2], drop=True) - r.sel(x=x[i1], drop=True)) / (
            x[i2] - x[i1]
        )
        # print(
        #     (i1, x[i1], r.sel(x=x[i1])),
        #     (i2, x[i2], r.sel(x=x[i2])),
        #     (i3, x[i3], r.sel(x=x[i3])),
        #     slope_int,
        #     slope_ext,
        # )
        assert_qty_allclose(slope_int, slope_ext)


@pytest.mark.parametrize(
    "name, kwargs",
    [
        ("input0.csv", dict(units="km")),
        # Units kwarg as a pint.Quantity
        ("input0.csv", dict(units=pint.get_application_registry()("1.0 km"))),
        # Dimensions as a container, without mapping
        ("input0.csv", dict(dims=["i", "j"], units="km")),
        #
        # Map a dimension name from the file to a different one in the quantity; ignore
        # dimension "foo"
        ("input1.csv", dict(dims=dict(i="i", j_dim="j"))),
        ("input2.csv", dict(dims=["i", "j"])),
        ("input2.csv", dict(dims=["i", "j"], units="km")),  # Logs a warning
        # Exceptions
        pytest.param(
            "input1.csv",
            dict(dims=dict(i="i", j_dim="j"), units="kg"),
            marks=pytest.mark.xfail(
                raises=ValueError, reason="Explicit units 'kg' do not match 'km'…"
            ),
        ),
        pytest.param(
            "load_file-invalid.csv",
            dict(),
            marks=pytest.mark.xfail(
                raises=ValueError, reason="with non-unique units array(['cm'], ['km'],"
            ),
        ),
    ],
)
def test_load_file(test_data_path, ureg, name, kwargs):
    qty = computations.load_file(test_data_path / name, name="baz", **kwargs)

    assert ("i", "j") == qty.dims
    assert ureg.kilometre == qty.units
    assert "baz" == qty.name


@pytest.mark.parametrize(
    "func",
    (
        computations.mul,
        computations.product,  # Alias
        computations.disaggregate_shares,  # Deprecated alias
    ),
)
def test_mul0(func):
    A = Quantity(xr.DataArray([1.0, 2], coords=[("a", ["a0", "a1"])]))
    B = Quantity(xr.DataArray([3.0, 4], coords=[("b", ["b0", "b1"])]))
    exp = Quantity(
        xr.DataArray(
            [[3.0, 4], [6, 8]],
            coords=[("a", ["a0", "a1"]), ("b", ["b0", "b1"])],
        ),
        units="1",
    )

    assert_qty_equal(exp, func(A, B))


@pytest.mark.parametrize("func", [computations.mul, computations.product])
@pytest.mark.parametrize(
    "dims, exp_dims, exp_shape",
    (
        # Scalar × scalar
        (({}, {}), tuple(), tuple()),
        # Scalar × 1D
        (({}, dict(a=2)), ("a",), (2,)),
        # 1D × scalar
        ((dict(a=2), {}), ("a",), (2,)),
        # 1D with disjoint dimensions ** 3 = 3D
        ((dict(a=2), dict(b=2), dict(c=2)), tuple("abc"), (2, 2, 2)),
        # 2D × scalar × scalar = 2D
        ((dict(a=2, b=2), {}, {}), tuple("ab"), (2, 2)),
        # scalar × 1D × scalar = 1D
        (({}, dict(a=2), {}), tuple("a"), (2,)),
        # 4D × 5D, with some overlapping dimensions
        (
            (dict(a=2, b=2, c=2, d=2), dict(b=2, c=2, d=2, e=2, f=2)),
            tuple("abcdef"),
            (2, 2, 2, 2, 2, 2),
        ),
    ),
)
def test_mul1(func, dims, exp_dims, exp_shape):
    """Product of quantities with disjoint and overlapping dimensions."""
    quantities = [random_qty(d) for d in dims]

    result = func(*quantities)

    assert exp_dims == result.dims
    assert exp_shape == result.shape


@pytest.mark.parametrize(
    "exponent, base_units, exp_units",
    (
        # 2D dimensionless ** float
        (1.2, None, None),
        # 2D with units ** int
        (2, "kg", "kg ** 2"),
        # 2D ** 1D int
        (pd.Series(dict(y1=1, y2=2, y3=3)), "kg", ""),
        # 2D ** 1D int, all values the same
        (pd.Series(dict(y1=2, y2=2, y3=2)), "kg", "kg ** 2"),
        # 2D ** 1D with units
        pytest.param(
            random_qty(dict(y=3), units="km"),
            None,
            None,
            marks=pytest.mark.xfail(
                raises=ValueError, reason="Cannot raise to a power with units (km)"
            ),
        ),
    ),
)
def test_pow_simple(ureg, exponent, base_units, exp_units):
    A = random_qty(dict(x=3, y=3), units=base_units)

    # Convert using the current Quantity class
    if isinstance(exponent, pd.Series):
        exponent = Quantity(exponent)

    result = computations.pow(A, exponent)
    assert exp_units is None or ureg.Unit(exp_units) == result.units


def test_pow(ureg):
    A = random_qty(dict(x=3, y=3))

    # 2D dimensionless ** int
    result = computations.pow(A, 2)
    # Expected values
    assert_qty_equal(A.sel(x="x1", y="y1") ** 2, result.sel(x="x1", y="y1"))

    # 2D ** 1D float
    B = random_qty(dict(y=3))
    result = computations.pow(A, B)
    # Expected values
    assert_allclose(
        A.sel(x="x1", y="y1").item() ** B.sel(y="y1").item(),
        result.sel(x="x1", y="y1").item(),
    )
    assert ureg.dimensionless == result.units


def test_relabel(data):
    # Unpack
    c, t, t_foo, t_bar, x = data

    # Mapping from old to new labels for each dimension
    args = dict(
        t={"foo2": "baz", "bar5": "qux", "nothing": "nothing"},
        y={2030: 3030},
        not_a_dimension=None,
    )

    def check(qty):
        # Dimension t was relabeled
        t_out = set(qty.coords["t"].data)
        assert {"baz", "qux"} < t_out and not {"foo2", "bar5"} & t_out
        # Dimension y was relabeled
        assert 3030 in result.coords["y"] and 2030 not in result.coords["y"]

    # Can be called with a dictionary
    result = computations.relabel(x, args)
    check(result)
    assert result.name == x.name and result.units == x.units  # Pass through

    # Can be added and used through Computer

    # Store the name map in the Computer
    c.add("labels", quote(args))

    # Test multiple ways of adding this computation
    for args in [
        ("test", computations.relabel, "x:t-y", args),
        ("test", partial(computations.relabel, **args), "x:t-y"),
        ("test", "relabel", "x:t-y", args),
        ("test", "relabel", "x:t-y", "labels"),
        # Deprecated
        ("relabel", "test", "x:t-y", args),
        ("relabel", "test", "x:t-y", "labels"),
    ]:
        c.add(*args)
        result = c.get("test")
        check(result)


def test_rename_dims(data):
    # Unpack
    c, t, t_foo, t_bar, x = data

    # Can be called with a dictionary
    args = {"t": "s", "y": "z"}
    result = computations.rename_dims(x, args)
    assert result.name == x.name and result.units == x.units  # Pass through
    assert ("s", "z") == result.dims  # Quantity has renamed dimensions
    assert all(t == result.coords["s"])  # Renamed dimension contain original labels

    # Can be called with keyword arguments
    result = computations.rename_dims(x, **args)
    assert ("s", "z") == result.dims and all(t == result.coords["s"])  # As above

    with pytest.raises(ValueError, match="cannot specify both keyword and positional"):
        computations.rename_dims(x, args, **args)

    # Can be added and used through Computer

    # Store the name map in the Computer
    c.add("dim name map", quote(args))

    # Test multiple ways of adding this computation
    for args in [
        ("test", computations.rename_dims, "x:t-y", args),
        ("test", partial(computations.rename_dims, **args), "x:t-y"),
        ("test", "rename_dims", "x:t-y", args),
        ("test", "rename_dims", "x:t-y", "dim name map"),
        # Deprecated
        ("rename_dims", "test", "x:t-y", args),
        ("rename_dims", "test", "x:t-y", "dim name map"),
    ]:
        c.add(*args)
        result = c.get("test")
        assert ("s", "z") == result.dims and all(t == result.coords["s"])  # As above


def test_round(data):
    # Unpack
    *_, x = data

    # Up to 36 unique random values in `x`
    assert 2 < len(x.to_series().unique()) <= 36

    # round() runs
    result0 = computations.round(x)
    assert result0.name == x.name and result0.units == x.units

    # Only 0 or 1
    assert {0.0, 1.0} >= set(result0.to_series().unique())

    # round to 1 decimal place
    result1 = computations.round(x, 1)
    assert 0 <= len(result1.to_series().unique()) <= 11


@pytest.mark.parametrize(
    "indexers, kwargs, exp_dims, exp_shape",
    (
        # Length-1 indexer but drop=False (default) results in 2D data
        ({"y": [2010]}, {}, ("t", "y"), (6, 1)),
        # Same, with an additional non-existent label → same result
        ({"y": [2010, 9999]}, {}, ("t", "y"), (6, 1)),
        # Scalar indexer with drop=True results in 1D data
        ({"y": 2010}, dict(drop=True), ("t",), (6,)),
        # Length-1 indexer with drop=True results in 2D data
        ({"y": [2010]}, dict(drop=True), ("t", "y"), (6, 1)),
        # Scalar indexer with nonexistent label -> KeyError
        pytest.param({"y": 9999}, {}, (), (), marks=pytest.mark.xfail(raises=KeyError)),
        # Length-1 indexer with nonexistent label
        # NB this gives shape (6, 0) with SparseDataArray; (0, 0) with AttrSeries; test
        #    the size instead
        ({"y": [9999]}, {}, ("t", "y"), 0),
        # With inverse=True, the given label is dropped from the given dimension
        ({"y": [2010]}, dict(inverse=True), ("t", "y"), (6, 6 - 1)),
    ),
)
def test_select0(data, indexers, kwargs, exp_dims, exp_shape) -> None:
    *_, x = data

    result = computations.select(x, indexers=indexers, **kwargs)

    assert exp_dims == result.dims
    if isinstance(exp_shape, tuple):
        assert exp_shape == result.shape
    else:
        assert exp_shape == result.size


def test_select1(data) -> None:
    # Unpack
    *_, t_foo, t_bar, x = data

    N_y = 6

    x = Quantity(x)
    assert x.size == 6 * N_y

    # Selection with inverse=False
    indexers: Mapping[Hashable, Iterable[Hashable]] = {"t": t_foo[0:1] + t_bar[0:1]}
    result_0 = computations.select(x, indexers=indexers)
    assert result_0.size == 2 * N_y
    assert result_0.name == x.name and result_0.units == x.units  # Pass through

    # Select with labels that do not appear in the data
    result_1 = computations.select(x, indexers={"t": t_foo + ["MISSING"]})
    assert result_1.size == len(t_foo) * N_y

    # Select with xarray indexers
    indexers = {
        "t": xr.DataArray(
            t_foo, dims="new_dim", coords={"new_dim": ["d1", "d2", "d3"]}
        ),
        "y": xr.DataArray(
            [2000, 2010, 2020], dims="new_dim", coords={"new_dim": ["d1", "d2", "d3"]}
        ),
    }
    # NB with pandas 2.1, this triggers the RecursionError fixed in khaeru/genno#99
    result_2 = computations.select(x, indexers)
    assert ("new_dim",) == result_2.dims

    with pytest.raises(NotImplementedError):
        computations.select(x, indexers, inverse=True)


def test_select_bigmem():
    """:func:`select` with large quantities does not exhaust memory."""
    # Create a Computer with large data
    c = Computer()
    keys = add_large_data(c, num_params=2, N_dims=17)

    # Add a task top generate random indexers
    def random_indexers(qty, *, dim_index=0, k=20):
        dims = qty.dims
        coords = qty.coords

        d = dims[dim_index]
        return {d: list(map(lambda c: c.item(), random.choices(coords[d], k=k)))}

    k = c.add("random indexers", random_indexers, keys[0])

    # Add a task to select some values
    key = c.add("test key", "select", keys[0], k)

    if Quantity._get_class() is SparseDataArray:
        # ValueError: invalid dims: array size defined by dims is larger than the
        # maximum possible size.
        pytest.xfail(reason="Too large for sparse")

    # Selection occurs without raising MemoryError or segfault
    result = c.get(key)

    # Result can be converted to pd.Series
    result.to_series()


def test_sub(data):
    *_, t_foo, t_bar, x = data

    # Function runs
    result = computations.sub(x, x)

    assert (0 == result).all()

    assert result.units == x.units  # Pass through


@pytest.mark.parametrize("dimensions", (["t"], ["y"], ["t", "y"]))
def test_sum(data, dimensions):
    *_, t_foo, t_bar, x = data

    # Function runs
    result = computations.sum(x, dimensions=dimensions)

    assert result.name == x.name and result.units == x.units  # Pass through
