"""Tests for genno.quantity."""
import re

import pandas as pd
import pint
import pytest
import xarray as xr

from genno import Computer, Quantity, computations
from genno.core.quantity import assert_quantity
from genno.testing import add_large_data, assert_qty_allclose, assert_qty_equal


@pytest.mark.usefixtures("parametrize_quantity_class")
class TestQuantity:
    """Tests of Quantity."""

    @pytest.fixture
    def a(self):
        da = xr.DataArray([0.8, 0.2], coords=[["oil", "water"]], dims=["p"])
        yield Quantity(da)

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

    def test_copy_modify(self, a):
        """Making a Quantity another produces a distinct attrs dictionary."""
        assert 0 == len(a.attrs)

        a.attrs["_unit"] = pint.Unit("km")

        b = Quantity(a, units="kg")
        assert pint.Unit("kg") == b.attrs["_unit"]

        assert pint.Unit("km") == a.attrs["_unit"]

    def test_to_dataframe(self, a):
        """Test Quantity.to_dataframe()."""
        assert isinstance(a.to_dataframe(), pd.DataFrame)

    def test_to_series(self, a):
        """Test .to_series() on child classes, and Quantity.from_series."""
        s = a.to_series()
        assert isinstance(s, pd.Series)

        Quantity.from_series(s)

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
