"""Tests for genno.quantity."""
import re

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from ixmp import Scenario  # FIXME avoid using this here

from genno import Quantity, computations
from genno.compat.ixmp.reporter import Reporter  # FIXME avoid using this here
from genno.core.quantity import assert_quantity
from genno.testing import assert_qty_allclose, assert_qty_equal


@pytest.mark.usefixtures("parametrize_quantity_class")
class TestQuantity:
    """Tests of Quantity."""

    @pytest.fixture
    def a(self):
        da = xr.DataArray([0.8, 0.2], coords=[["oil", "water"]], dims=["p"])
        yield Quantity(da)

    @pytest.fixture(scope="class")
    def scen_with_big_data(self, test_mp, num_params=10):
        from itertools import zip_longest

        # test_mp.add_unit('kg')
        scen = Scenario(test_mp, "TestQuantity", "big data", version="new")

        # Dimensions and their lengths (Fibonacci numbers)
        N_dims = 6
        dims = "abcdefgh"[: N_dims + 1]
        sizes = [1, 5, 21, 21, 89, 377, 1597, 6765][: N_dims + 1]

        # commented: "377 / 73984365 elements = 0.00051% full"
        # from functools import reduce
        # from operator import mul
        # size = reduce(mul, sizes)
        # print('{} / {} elements = {:.5f}% full'
        #       .format(max(sizes), size, 100 * max(sizes) / size))

        # Names like f_0000 ... f_1596 along each dimension
        coords = []
        for d, N in zip(dims, sizes):
            coords.append([f"{d}_{i:04d}" for i in range(N)])
            # Add to Scenario
            scen.init_set(d)
            scen.add_set(d, coords[-1])

        def _make_values():
            """Make a DataFrame containing each label in *coords* ≥ 1 time."""
            values = list(zip_longest(*coords, np.random.rand(max(sizes))))
            result = pd.DataFrame(values, columns=list(dims) + ["value"]).ffill()
            result["unit"] = "kg"
            return result

        # Fill the Scenario with quantities named q_01 ... q_09
        names = []
        for i in range(num_params):
            name = f"q_{i:02d}"
            scen.init_par(name, list(dims))
            scen.add_par(name, _make_values())
            names.append(name)

        yield scen

    @pytest.mark.filterwarnings(
        "ignore:.*default dtype for empty Series.*:DeprecationWarning"
    )
    def test_init(self):
        """Instantiated from a scalar object."""
        Quantity(object())

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

    def test_to_dataframe(self, a):
        """Test Quantity.to_dataframe()."""
        assert isinstance(a.to_dataframe(), pd.DataFrame)

    def test_size(self, scen_with_big_data):
        """Stress-test reporting of large, sparse quantities."""
        scen = scen_with_big_data

        # Create the Reporter
        rep = Reporter.from_scenario(scen)

        # Add a task to compute the product, i.e. requires all the q_*
        keys = [rep.full_key(name) for name in scen.par_list()]
        rep.add("bigmem", tuple([computations.product] + keys))

        # One quantity fits in memory
        rep.get(keys[0])

        # All quantities can be multiplied without raising MemoryError
        result = rep.get("bigmem")

        # Result can be converted to pd.Series
        result.to_series()
