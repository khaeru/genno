import logging

import numpy as np
import pint
import pytest
import xarray as xr
from pandas.testing import assert_series_equal

from genno import Computer, Quantity, computations
from genno.testing import add_test_data2, assert_logs, assert_qty_equal, random_qty

pytestmark = pytest.mark.usefixtures("parametrize_quantity_class")


@pytest.fixture(scope="function")
def data():
    """Yields a computer, then the values of :func:`.add_test_data2`."""
    c = Computer()
    yield [c] + list(add_test_data2(c))


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


def test_concat(data):
    *_, t_foo, t_bar, x = data

    # Split x into two concatenateable quantities
    computations.concat(
        computations.select(x, dict(t=t_foo)),
        computations.select(x, dict(t=t_bar)),
        dim="t",
    )


@pytest.mark.parametrize(
    "name, kwargs",
    [
        ("input0.csv", dict(units="km")),
        # Map a dimension name from the file to a different one in the quantity; ignore
        # dimension "foo"
        ("input1.csv", dict(dims=dict(i="i", j_dim="j"))),
        # Dimensions as a container, without mapping
        ("input0.csv", dict(dims=["i", "j"], units="km")),
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
    # TODO test name= parameter
    qty = computations.load_file(test_data_path / name, **kwargs)

    assert ("i", "j") == qty.dims
    assert ureg.kilometre == qty.attrs["_unit"]


@pytest.mark.xfail(reason="Outer join of non-intersecting dimensions (AttrSeries only)")
def test_product0():
    A = Quantity(xr.DataArray([1.0, 2], coords=[("a", ["a0", "a1"])]))
    B = Quantity(xr.DataArray([3.0, 4], coords=[("b", ["b0", "b1"])]))
    exp = Quantity(
        xr.DataArray(
            [[3.0, 4], [6, 8]],
            coords=[("a", ["a0", "a1"]), ("b", ["b0", "b1"])],
        ),
        units="1",
    )

    assert_qty_equal(exp, computations.product(A, B))
    computations.product(exp, B)


def test_product1():
    """Product of quantities with overlapping dimensions."""
    A = random_qty(dict(a=2, b=2, c=2, d=2))
    B = random_qty(dict(b=2, c=2, d=2, e=2, f=2))

    assert computations.product(A, B).size == 2 ** 6


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
    indexers["y"] = "2010"
    result_1 = computations.select(x, indexers=indexers)
    assert result_1.size == 2 * 1

    # Selection with inverse=True
    result_2 = computations.select(x, indexers=indexers, inverse=True)
    assert result_2.size == 4 * 5
