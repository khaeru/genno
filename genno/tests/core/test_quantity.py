"""Tests for genno.quantity."""
import logging
import operator
import re

import pandas as pd
import pint
import pytest
import xarray as xr
from numpy import nan
from pytest import param

from genno import Computer, Quantity, computations
from genno.core.attrseries import AttrSeries
from genno.core.quantity import assert_quantity
from genno.core.sparsedataarray import SparseDataArray
from genno.testing import add_large_data, assert_qty_allclose, assert_qty_equal


@pytest.mark.usefixtures("parametrize_quantity_class")
class TestQuantity:
    """Tests of Quantity."""

    @pytest.fixture
    def a(self):
        yield Quantity(xr.DataArray([0.8, 0.2], coords=[["oil", "water"]], dims=["p"]))

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
    def test_init(self, args, kwargs):
        """Instantiated from a scalar object."""
        Quantity(*args, **kwargs)

    def test_assert(self, a):
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

    def test_assert_with_attrs(self, a):
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

    def test_assign_coords(self, a):
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

    def test_bfill(self, tri):
        """Test Quantity.bfill()."""
        if Quantity._get_class() is SparseDataArray:
            pytest.xfail(reason="sparse.COO.flip() not implemented")

        r1 = tri.bfill("x")
        assert r1.loc["x0", "y0"] == tri.loc["x2", "y0"]

        r2 = tri.bfill("y")
        assert r2.loc["x0", "y0"] == tri.loc["x0", "y2"]

    def test_coords(self, tri):
        assert isinstance(tri.coords, xr.core.coordinates.Coordinates)
        assert ["x", "y"] == list(tri.coords)

    def test_copy_modify(self, a):
        """Making a Quantity another produces a distinct attrs dictionary."""
        assert 0 == len(a.attrs)

        a.attrs["_unit"] = pint.Unit("km")

        b = Quantity(a, units="kg")
        assert pint.Unit("kg") == b.attrs["_unit"]

        assert pint.Unit("km") == a.attrs["_unit"]

    def test_cumprod(self, caplog, tri):
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

    def test_drop_vars(self, a):
        a.expand_dims({"phase": ["liquid"]}).drop_vars("phase")

    def test_expand_dims(self, a):
        # Single label on a new dimension
        q0 = a.expand_dims({"phase": ["liquid"]})
        assert ("phase", "p") == q0.dims

        # Multiple labels
        q1 = a.expand_dims({"phase": ["liquid", "solid"]})
        assert ("phase", "p") == q1.dims
        assert all(["liquid", "solid"] == q1.coords["phase"])

        # Multiple dimensions and labels
        q2 = a.expand_dims({"colour": ["red", "blue"], "phase": ["liquid", "solid"]})
        assert ("colour", "phase", "p") == q2.dims

    def test_ffill(self, tri):
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

    def test_sel(self, tri):
        # Create indexers
        newdim = [("newdim", ["nd0", "nd1", "nd2"])]
        x_idx = xr.DataArray(["x2", "x1", "x2"], coords=newdim)
        y_idx = xr.DataArray(["y4", "y2", "y0"], coords=newdim)

        # Select using the indexers
        assert_qty_equal(
            Quantity(xr.DataArray([9.0, 3.0, 5.0], coords=newdim), units="kg"),
            tri.sel(x=x_idx, y=y_idx),
            ignore_extra_coords=True,
        )

        # Exception raised for mismatched lengths
        with pytest.raises(IndexError, match="Dimensions of indexers mismatch"):
            tri.sel(x=x_idx[:-1], y=y_idx)

    def test_shift(self, tri):
        """Test Quantity.shift()."""
        if Quantity._get_class() is SparseDataArray:
            pytest.xfail(reason="sparse.COO.pad() not implemented")

        r1 = tri.shift(x=1)
        assert r1.loc["x2", "y1"] == tri.loc["x1", "y1"]

        r2 = tri.shift(y=2)
        assert r2.loc["x2", "y4"] == tri.loc["x2", "y2"]

        with pytest.raises(NotImplementedError):
            # AttrSeries only
            tri.shift(x=1, y=2)

    def test_size(self):
        """Stress-test reporting of large, sparse quantities."""
        # Create the Reporter
        c = Computer()

        # Prepare large data, store the keys of the quantities
        keys = add_large_data(c, num_params=10)

        # Add a task to compute the product, i.e. requires all the q_*
        c.add("bigmem", tuple([computations.product] + keys))

        # One quantity fits in memory
        c.get(keys[0])

        # All quantities can be multiplied without raising MemoryError
        result = c.get("bigmem")

        # Result can be converted to pd.Series
        result.to_series()

    def test_to_dataframe(self, a):
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

    def test_to_series(self, a):
        """Test .to_series() on child classes, and Quantity.from_series."""
        s = a.to_series()
        assert isinstance(s, pd.Series)

        Quantity.from_series(s)

    def test_units(self, a):
        # Units can be retrieved; dimensionless by default
        assert a.units.dimensionless

        # Set with a string results in a pint.Unit instance
        a.units = "kg"
        assert pint.Unit("kg") == a.units

        # Can be set to dimensionless
        a.units = ""
        assert a.units.dimensionless

    @pytest.mark.parametrize(
        "op", [operator.add, operator.mul, operator.sub, operator.truediv]
    )
    @pytest.mark.parametrize("type_", [int, float, param(str, marks=pytest.mark.xfail)])
    def test_arithmetic(self, op, type_, a):
        """Quantity can be added to int or float."""
        result = op(type_(4.2), a)

        assert (2,) == result.shape
        assert a.dtype == result.dtype
