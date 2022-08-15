import logging
import re
from functools import partial

import numpy as np
import pandas as pd
import pint
import pytest
import xarray as xr
from dask.core import quote
from pandas.testing import assert_series_equal

from genno import Computer, Quantity, computations
from genno.testing import (
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
        units=x.attrs["_unit"],
    )
    b = Quantity(
        xr.DataArray(
            np.random.rand(len(t_bar), len(y)), coords=[t_bar, y], dims=["t", "y"]
        ),
        units=x.attrs["_unit"],
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
def test_aggregate(data, keep):
    *_, t_foo, t_bar, x = data

    computations.aggregate(x, dict(t=dict(foo=t_foo, bar=t_bar)), keep)
    # TODO expand with assertions


def test_apply_units(data, caplog):
    # Unpack
    *_, x = data

    registry = pint.get_application_registry()

    # Brute-force replacement with incompatible units
    with assert_logs(
        caplog, "Replace 'kilogram' with incompatible 'liter'", at_level=logging.DEBUG
    ):
        result = computations.apply_units(x, "litres")
    assert result.attrs["_unit"] == registry.Unit("litre")
    # No change in values
    assert_series_equal(result.to_series(), x.to_series())

    # Compatible units: magnitudes are also converted
    with assert_logs(
        caplog, "Convert 'kilogram' to 'metric_ton'", at_level=logging.DEBUG
    ):
        result = computations.apply_units(x, "tonne")
    assert result.attrs["_unit"] == registry.Unit("tonne")
    assert_series_equal(result.to_series(), x.to_series() * 0.001)

    # Remove unit
    x.attrs["_unit"] = registry.Unit("dimensionless")

    caplog.clear()
    result = computations.apply_units(x, "kg")
    # Nothing logged when _unit attr is missing
    assert len(caplog.messages) == 0
    assert result.attrs["_unit"] == registry.Unit("kg")
    assert_series_equal(result.to_series(), x.to_series())


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


def test_concat(data):
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


@pytest.mark.parametrize("func", [computations.div, computations.ratio])
def test_div(func, ureg):
    # Non-overlapping dimensions can be broadcast together
    A = random_qty(dict(x=3, y=4), units="km")
    B = random_qty(dict(z=2), units="hour")

    result = func(A, B)
    assert ("x", "y", "z") == result.dims
    assert ureg.Unit("km / hour") == result.attrs["_unit"]


def test_group_sum(ureg):
    a = "a1 a2".split()
    b = "b1 b2 b3".split()
    X = Quantity(
        xr.DataArray(np.random.rand(2, 3), coords=[("a", a), ("b", b)]),
        units=ureg.kg,
    )

    result = computations.group_sum(X, "a", "b")
    assert ("a",) == result.dims
    assert 2 == len(result)


def test_index_to():
    q = random_qty(dict(x=3, y=5))
    q.name = "Foo"

    exp = q / q.sel(x="x0")
    exp.units = ""

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
def test_interpolate(caplog, shape):
    """Test :func:`.interpolate`."""
    # Generate a random quantity with one dimension indexed by integers
    q = random_qty(shape)
    x = [2020, 2030, 2040]
    q = q.assign_coords({"x": x})

    # Linear interpolation of 1 point
    result = computations.interpolate(q, dict(x=2025), assume_sorted=False)
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


@pytest.mark.parametrize("func", [computations.mul, computations.product])
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
    "dims, exp_size",
    (
        # Some overlapping dimensions
        ((dict(a=2, b=2, c=2, d=2), dict(b=2, c=2, d=2, e=2, f=2)), 2**6),
        # 1D with disjoint dimensions ** 3 = 3D
        ((dict(a=2), dict(b=2), dict(c=2)), 2**3),
        # 2D × scalar × scalar = 2D
        ((dict(a=2, b=2), dict(), dict()), 4),
        # scalar × 1D × scalar = 1D
        # XFAIL for AttrSeries, XPASS for SparseDataArray
        pytest.param((dict(), dict(a=2), dict()), 2, marks=pytest.mark.xfail),
    ),
)
def test_mul1(func, dims, exp_size):
    """Product of quantities with disjoint and overlapping dimensions."""
    quantities = [random_qty(d) for d in dims]

    result = func(*quantities)

    assert exp_size == result.size


def test_pow(ureg):
    # 2D dimensionless ** int
    A = random_qty(dict(x=3, y=3))
    result = computations.pow(A, 2)

    # Expected values
    assert_qty_equal(A.sel(x="x1", y="y1") ** 2, result.sel(x="x1", y="y1"))

    # 2D with units ** int
    A = random_qty(dict(x=3, y=3), units="kg")
    result = computations.pow(A, 2)

    # Expected units
    assert ureg.kg**2 == result.attrs["_unit"]

    # 2D ** 1D
    B = random_qty(dict(y=3))

    result = computations.pow(A, B)

    # Expected values
    assert (
        A.sel(x="x1", y="y1").item() ** B.sel(y="y1").item()
        == result.sel(x="x1", y="y1").item()
    )
    assert ureg.dimensionless == result.attrs["_unit"]

    # 2D ** 1D with units
    C = random_qty(dict(y=3), units="km")

    with pytest.raises(
        ValueError, match=re.escape("Cannot raise to a power with units (km)")
    ):
        computations.pow(A, C)


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

    # Can be added and used through Computer

    # Store the name map in the Computer
    c.add("labels", quote(args))

    # Test multiple ways of adding this computation
    for args in [
        ("test", computations.relabel, "x:t-y", args),
        ("test", partial(computations.relabel, **args), "x:t-y"),
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
        ("rename_dims", "test", "x:t-y", args),
        ("rename_dims", "test", "x:t-y", "dim name map"),
    ]:
        c.add(*args)
        result = c.get("test")
        assert ("s", "z") == result.dims and all(t == result.coords["s"])  # As above


def test_select(data):
    # Unpack
    *_, t_foo, t_bar, x = data

    x = Quantity(x)
    assert x.size == 6 * 6

    # Selection with inverse=False
    indexers = {"t": t_foo[0:1] + t_bar[0:1]}
    result_0 = computations.select(x, indexers=indexers)
    assert result_0.size == 2 * 6

    # Single indexer along one dimension results in 1D data
    indexers["y"] = [2010]
    result_1 = computations.select(x, indexers=indexers)
    assert result_1.size == 2 * 1

    # Selection with inverse=True
    result_2 = computations.select(x, indexers=indexers, inverse=True)
    assert result_2.size == 4 * 5
