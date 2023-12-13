"""Tests for genno.quantity."""
import logging
import operator
import re

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pint
import pytest
import xarray as xr
from numpy import nan
from pytest import param

import genno.operator
from genno import Computer, Quantity
from genno.core.attrseries import AttrSeries
from genno.core.quantity import assert_quantity, possible_scalar, unwrap_scalar
from genno.core.sparsedataarray import SparseDataArray
from genno.testing import (
    add_large_data,
    assert_qty_allclose,
    assert_qty_equal,
    assert_units,
)

pytestmark = pytest.mark.usefixtures("parametrize_quantity_class")

SUPPORTED_BINOPS = [
    operator.add,
    operator.mul,
    operator.sub,
    operator.truediv,
]


class TestQuantity:
    """Tests of Quantity."""

    @pytest.fixture
    def a(self):
        yield Quantity(xr.DataArray([0.8, 0.2], coords=[["oil", "water"]], dims=["p"]))

    @pytest.fixture
    def foo(self):
        # NB 0.0 because sparse cannot handle data that is all int
        yield Quantity(
            xr.DataArray(
                [[0.0, 1], [2, 3]],
                coords=[("a", ["a1", "a2"]), ("b", ["b1", "b2"])],
                name="Foo",
            ),
            units="kg",
        )

    @pytest.fixture()
    def tri(self):
        """Fixture returning triangular data to test fill, shift, etc."""
        return Quantity(
            xr.DataArray(
                [
                    [nan, nan, 1.0, nan, nan],
                    [nan, 2, 3, 4, nan],
                    [5, 6, 7, 8, 9],
                ],
                coords=[
                    ("x", ["x0", "x1", "x2"]),
                    ("y", ["y0", "y1", "y2", "y3", "y4"]),
                ],
            ),
            units="kg",
        )

    @pytest.mark.parametrize(
        "args, kwargs",
        (
            # Integer, converted to float() for sparse
            ((3,), dict(units="kg")),
            # Scalar object
            ((object(),), dict(units="kg")),
            # pd.Series
            ((pd.Series([0, 1], index=["a", "b"], name="foo"),), dict(units="kg")),
            # pd.DataFrame
            (
                (pd.DataFrame([[0], [1]], index=["a", "b"], columns=["foo"]),),
                dict(units="kg"),
            ),
            pytest.param(
                (
                    pd.DataFrame(
                        [[0, 1], [2, 3]], index=["a", "b"], columns=["foo", "bar"]
                    ),
                ),
                dict(units="kg"),
                marks=pytest.mark.xfail(raises=TypeError),
            ),
        ),
    )
    def test_init(self, args, kwargs) -> None:
        """Instantiated from a scalar object."""
        Quantity(*args, **kwargs)

    def test_assert(self, a) -> None:
        """Test assertions about Quantity.

        These are tests without `attr` property, in which case direct pd.Series
        and xr.DataArray comparisons are possible.
        """
        with pytest.raises(
            TypeError,
            match=re.escape("arg #2 ('foo') is not Quantity; likely an incorrect key"),
        ):
            assert_quantity(a, "foo")

        # Convert to pd.Series
        b = a.to_series()

        assert_qty_equal(a, b, check_type=False)
        assert_qty_equal(b, a, check_type=False)
        assert_qty_allclose(a, b, check_type=False)
        assert_qty_allclose(b, a, check_type=False)

        c = Quantity(a)

        assert_qty_equal(a, c, check_type=True)
        assert_qty_equal(c, a, check_type=True)
        assert_qty_allclose(a, c, check_type=True)
        assert_qty_allclose(c, a, check_type=True)

    def test_assert_with_attrs(self, a) -> None:
        """Test assertions about Quantity with attrs.

        Here direct pd.Series and xr.DataArray comparisons are *not* possible.
        """
        attrs = {"foo": "bar"}
        a.attrs = attrs

        b = Quantity(a)

        # make sure it has the correct property
        assert a.attrs == attrs
        assert b.attrs == attrs

        assert_qty_equal(a, b)
        assert_qty_equal(b, a)
        assert_qty_allclose(a, b)
        assert_qty_allclose(b, a)

        # check_attrs=False allows a successful equals assertion even when the
        # attrs are different
        a.attrs = {"bar": "foo"}
        assert_qty_equal(a, b, check_attrs=False)

    def test_assign_coords(self, a) -> None:
        # Relabel an existing dimension
        q1 = a.assign_coords({"p": ["apple", "orange"]})
        assert ("p",) == q1.dims
        assert all(["apple", "orange"] == q1.coords["p"])

        # Exception raised when the values are of the wrong length
        with pytest.raises(
            ValueError,
            match="conflicting sizes for dimension 'p': length 2 .* and length 3",
        ):
            a.assign_coords({"p": ["apple", "orange", "banana"]})
        with pytest.raises(
            ValueError,
            match="conflicting sizes for dimension 'p': length 2 .* and length 1",
        ):
            a.assign_coords({"p": ["apple"]})

    def test_astype(self, tri) -> None:
        result = tri.astype(float)
        assert float == result.dtype

    def test_bfill(self, tri) -> None:
        """Test Quantity.bfill()."""
        if Quantity._get_class() is SparseDataArray:
            pytest.xfail(reason="sparse.COO.flip() not implemented")

        r1 = tri.bfill("x")
        assert r1.loc["x0", "y0"] == tri.loc["x2", "y0"]

        r2 = tri.bfill("y")
        assert r2.loc["x0", "y0"] == tri.loc["x0", "y2"]

    def test_coords(self, tri) -> None:
        coords = tri.coords
        assert isinstance(coords, xr.core.coordinates.Coordinates)
        assert ["x", "y"] == list(coords)
        assert "x" in coords  # __contains__

        assert isinstance(coords["x"], xr.DataArray)

        coords = Quantity(3, units="kg").coords
        assert [] == list(coords)

    def test_copy_modify(self, a) -> None:
        """Making a Quantity another produces a distinct attrs dictionary."""
        assert 0 == len(a.attrs)

        a.units = pint.Unit("km")

        b = Quantity(a, units="kg")
        assert pint.Unit("kg") == b.units

        assert pint.Unit("km") == a.units

    def test_cumprod(self, caplog, tri) -> None:
        """Test Quantity.cumprod()."""
        if Quantity._get_class() is SparseDataArray:
            pytest.xfail(reason="sparse.COO.nancumprod() not implemented")

        caplog.set_level(logging.INFO)

        args = dict(axis=123) if Quantity._get_class() is AttrSeries else dict()
        r1 = tri.cumprod("x", **args)
        assert 1 * 3 * 7 == r1.loc["x2", "y2"]
        if Quantity._get_class() is AttrSeries:
            assert ["AttrSeries.cumprod(…, axis=…) is ignored"] == caplog.messages

        r2 = tri.cumprod("y")
        assert 2 * 3 == r2.loc["x1", "y2"]
        assert 5 * 6 * 7 * 8 * 9 == r2.loc["x2", "y4"]

    def test_drop_vars(self, a) -> None:
        a.expand_dims({"phase": ["liquid"]}).drop_vars("phase")

    def test_expand_dims(self, a) -> None:
        # Single label on a new dimension
        q0 = a.expand_dims({"phase": ["liquid"]})
        assert ("phase", "p") == q0.dims

        # New dimension(s) without labels
        q1 = a.expand_dims(["phase"])
        assert ("phase", "p") == q1.dims
        assert 2 == q1.size
        assert (1, 2) == q1.shape

        # New dimension(s) without labels
        q2 = a.expand_dims({"phase": []})
        assert ("phase", "p") == q2.dims
        if Quantity._get_class() is AttrSeries:
            # NB this behaviour differs slightly from xr.DataArray.expand_dims()
            assert (1, 2) == q2.shape
            assert 2 == q2.size
        else:
            # da = xr.DataArray([0.8, 0.2], coords=[["oil", "water"]], dims=["p"])
            # assert (0, 2) == da.expand_dims({"phase": []}).shape  # Different result
            # assert (1, 2) == da.expand_dims(["phase"]).shape  # Same result

            assert (0, 2) == q2.shape
            assert 0 == q2.size

        # Multiple labels
        q3 = a.expand_dims({"phase": ["liquid", "solid"]})
        assert ("phase", "p") == q3.dims
        assert all(["liquid", "solid"] == q3.coords["phase"])

        # Multiple dimensions and labels
        q4 = a.expand_dims({"colour": ["red", "blue"], "phase": ["liquid", "solid"]})
        assert ("colour", "phase", "p") == q4.dims

    def test_ffill(self, tri) -> None:
        """Test Quantity.ffill()."""

        # Forward fill along "x" dimension results in no change
        r1 = tri.ffill("x")
        assert_qty_equal(tri, r1)

        # Forward fill along y dimension works
        r2 = tri.ffill("y")

        # Check some filled values
        assert (
            r2.loc["x0", "y4"].item()
            == r2.loc["x0", "y3"].item()
            == tri.loc["x0", "y2"].item()
        )

    @pytest.mark.parametrize(
        "left, right", (["float", "qty"], ["qty", "float"], ["qty", "qty"])
    )
    @pytest.mark.parametrize("op", SUPPORTED_BINOPS)
    def test_operation(self, left, op, right, tri: Quantity) -> None:
        """Test the standard binary operations +, -, *, /."""
        values = {"float": 1.0, "qty": tri}
        left = values[left]
        right = values[right]

        # Binary operation succeeds
        result = op(left, right)

        # Result is of the expected type
        assert isinstance(result, tri.__class__), type(result)

    @pytest.mark.parametrize("op", SUPPORTED_BINOPS)
    @pytest.mark.parametrize("type_", [int, float, param(str, marks=pytest.mark.xfail)])
    def test_operation_scalar(self, op, type_, a) -> None:
        """Quantity can be added to int or float."""
        result = op(type_(4.2), a)

        # Result has the expected shape
        assert (2,) == result.shape
        assert a.dtype == result.dtype

    @pytest.mark.parametrize(
        "op, left_units, right_units, exp_units",
        (
            (operator.add, "", "", ""),  # Both dimensionless
            (operator.add, "kg", "kg", "kg"),  # Same units
            (operator.add, "", "kg", ""),  # Different units—discarded
            (operator.sub, "", "", ""),  # Both dimensionless
            (operator.sub, "kg", "kg", "kg"),  # Same units
            (operator.sub, "", "kg", ""),  # Different units—discarded
            (operator.mul, "", "", ""),  # Both dimensionless
            (operator.mul, "", "kg", "kg"),  # One dimensionless
            (operator.mul, "kg", "kg", "kg **2"),  # Same units
            (operator.mul, "kg", "litre", "kg * litre"),  # Different units
            (operator.truediv, "", "", ""),  # Both dimensionless
            (operator.truediv, "kg", "", "kg"),  # Denominator dimensionless
            (operator.truediv, "", "kg", "1 / kg"),  # Numerator dimensionless
            (operator.truediv, "kg", "kg", ""),  # Same units
            (operator.truediv, "kg", "litre", "kg / litre"),  # Different units
        ),
    )
    def test_operation_units(
        self, a: Quantity, op, left_units, right_units, exp_units
    ) -> None:
        """Test units pass through the standard binary operations +, -, *, /."""
        left = Quantity(a, units=left_units)
        right = Quantity(a, units=right_units)

        # Binary operation succeeds
        result = op(left, right)

        # Result is of the expected type
        assert isinstance(result, a.__class__), type(result)

        # Result has the expected units
        assert_units(result, exp_units)

    def test_pipe(self, ureg, tri) -> None:
        result = tri.pipe(genno.operator.assign_units, "km")
        assert ureg.Unit("km") == result.units

    @pytest.mark.parametrize(
        "args, dropped",
        (
            (dict(x="x1"), True),  # default drop=False
            (dict(x=["x1"]), False),  # default drop=False
            (dict(x="x1", drop=False), True),
            (dict(x=["x1"], drop=False), False),
            (dict(x="x1", drop=True), True),
            (dict(x=["x1"], drop=True), False),
        ),
    )
    def test_sel(self, tri, args, dropped) -> None:
        result = tri.sel(**args)

        assert ({"y"} if dropped else {"x", "y"}) == set(result.dims)

    def test_sel_xarray(self, tri) -> None:
        """xarray-style indexing works."""
        # Create indexers
        newdim = [("newdim", ["nd0", "nd1", "nd2"])]
        x_idx = xr.DataArray(["x2", "x1", "x2"], coords=newdim)
        y_idx = xr.DataArray(["y4", "y2", "y0"], coords=newdim)

        # Select using the indexers
        # NB with pandas 2.1, this triggers the RecursionError fixed in khaeru/genno#99
        assert_qty_equal(
            Quantity(xr.DataArray([9.0, 3.0, 5.0], coords=newdim), units="kg"),
            tri.sel(x=x_idx, y=y_idx),
            ignore_extra_coords=True,
        )

        # Exception raised for mismatched lengths
        with pytest.raises(IndexError, match="Dimensions of indexers mismatch"):
            tri.sel(x=x_idx[:-1], y=y_idx)

    def test_shift(self, tri) -> None:
        """Test Quantity.shift()."""
        if Quantity._get_class() is SparseDataArray:
            pytest.xfail(reason="sparse.COO.pad() not implemented")

        r1 = tri.shift(x=1)
        assert r1.loc["x2", "y1"] == tri.loc["x1", "y1"]

        r2 = tri.shift(y=2)
        assert r2.loc["x2", "y4"] == tri.loc["x2", "y2"]

        r3 = tri.shift(x=1, y=2)
        assert r3.loc["x2", "y4"] == tri.loc["x1", "y2"]

    def test_size(self) -> None:
        """Stress-test reporting of large, sparse quantities."""
        # Create the Reporter
        c = Computer()

        # Prepare large data, store the keys of the quantities
        keys = add_large_data(c, num_params=10)

        # Add a task to compute the product, i.e. requires all the q_*
        c.add("bigmem", tuple([genno.operator.mul] + keys))

        # One quantity fits in memory
        c.get(keys[0])

        if Quantity._get_class() is SparseDataArray:
            pytest.xfail(
                reason='"IndexError: Only one-dimensional iterable indices supported." '
                "in sparse._coo.indexing"
            )

        # All quantities can be multiplied without raising MemoryError
        result = c.get("bigmem")

        # Result can be converted to pd.Series
        result.to_series()

    @pytest.mark.parametrize(
        "sel_kw, dims, values",
        (
            (dict(a=["a1"]), ("b",), [0, 1]),
            (dict(a="a1"), ("b",), [0, 1]),
            (dict(a="a2", b="b1"), (), [2]),
            (dict(a=["a2"], b="b1"), (), [2]),
            (dict(a=["a2"], b=["b1"]), (), [2]),
        ),
    )
    def test_squeeze0(self, foo, sel_kw, dims, values) -> None:
        # Method succeeds
        result = foo.sel(**sel_kw).squeeze()

        # Dimensions as expected
        assert dims == result.dims

        # Values as expected
        pdt.assert_series_equal(
            pd.Series(values, name="Foo"),
            result.to_series(),
            check_series_type=False,
            check_index=False,
            check_dtype=False,
        )

    @pytest.mark.parametrize(
        "dim, exc_type, match",
        (
            (
                "b",
                ValueError,
                "dimension to squeeze out which has length greater than one",
            ),
            ("c", KeyError, "c"),
        ),
    )
    def test_squeeze1(self, foo, dim, exc_type, match) -> None:
        with pytest.raises(exc_type, match=match):
            print(foo.squeeze(dim=dim))

    def test_to_dataframe(self, a) -> None:
        """Test Quantity.to_dataframe()."""
        # Returns pd.DataFrame
        result = a.to_dataframe()
        assert isinstance(result, pd.DataFrame)

        # "value" is used as a column name
        assert ["value"] == result.columns

        # Explicitly passed name produces a named column
        assert ["foo"] == a.to_dataframe("foo").columns

        with pytest.raises(NotImplementedError):
            a.to_dataframe(dim_order=["foo", "bar"])

    def test_to_series(self, a) -> None:
        """Test .to_series() on child classes, and Quantity.from_series."""
        s = a.to_series()
        assert isinstance(s, pd.Series)

        Quantity.from_series(s)

    def test_units(self, a: Quantity) -> None:
        # Units can be retrieved; dimensionless by default
        assert a.units.dimensionless

        # Set with a string results in a pint.Unit instance
        a.units = "kg"
        assert pint.Unit("kg") == a.units

        # Can be set to dimensionless
        a.units = ""
        assert a.units.dimensionless  # type: ignore [attr-defined]


@pytest.mark.parametrize(
    "value",
    [
        2,
        # Fails for SparseDataArray, not AttrSeries
        pytest.param(np.int64(2), marks=pytest.mark.xfail(raises=ValueError)),
        1.1,
        np.float64(1.1),
        pytest.param([0.1, 2.3], marks=pytest.mark.xfail(raises=AssertionError)),
    ],
)
def test_possible_scalar(value):
    tmp = possible_scalar(value)
    assert isinstance(tmp, Quantity), type(tmp)
    assert tuple() == tmp.dims

    assert value == unwrap_scalar(tmp)
