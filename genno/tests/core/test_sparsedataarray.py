from typing import cast

import pandas as pd
import pytest
import xarray as xr
from xarray.testing import assert_equal as assert_xr_equal

from genno import Computer
from genno.core.quantity import Quantity
from genno.core.sparsedataarray import HAS_SPARSE, SparseDataArray
from genno.testing import add_test_data, random_qty

pytestmark = pytest.mark.skipif(
    condition=not HAS_SPARSE,
    reason="`sparse` not available → can't test SparseDataArray",
)


def test_sda_accessor():
    """Test conversion to sparse.COO-backed xr.DataArray."""
    x_series = pd.Series(
        data=[1.0, 2, 3, 4],
        index=pd.MultiIndex.from_product(
            [["a", "b"], ["c", "d"]], names=["foo", "bar"]
        ),
    )
    y_series = pd.Series(data=[5.0, 6], index=pd.Index(["e", "f"], name="baz"))

    x = SparseDataArray.from_series(x_series)
    y = SparseDataArray.from_series(y_series)

    x_dense = x._sda.dense_super
    y_dense = y._sda.dense_super
    assert not x_dense._sda.COO_data or x_dense._sda.nan_fill
    assert not y_dense._sda.COO_data or y_dense._sda.nan_fill

    # As of sparse 0.10, sparse `y` is automatically broadcast to `x_dense`
    # Previously, this raised ValueError.
    x_dense * y

    z1 = x_dense._sda.convert() * y

    z2 = x * y_dense._sda.convert()
    assert z1.dims == ("foo", "bar", "baz") == z2.dims
    assert_xr_equal(z1, z2)

    z3 = x._sda.convert() * y._sda.convert()
    assert_xr_equal(z1, z3)

    z4 = x._sda.convert() * y
    assert_xr_equal(z1, z4)

    z5 = SparseDataArray.from_series(x_series) * y
    assert_xr_equal(z1, z5)


@pytest.mark.usefixtures("quantity_is_sparsedataarray")
class TestSparseDataArray:
    def test_init(self, caplog) -> None:
        """SDA can be initialized with integer data; a warning is logged."""
        SparseDataArray([[0, 1], [2, 3]])
        assert "Force dtype int64 → float" in caplog.messages

    def test_item(self) -> None:
        with pytest.raises(ValueError, match="can only convert an array of size 1"):
            random_qty(dict(x=2)).item()

        assert (
            0 <= random_qty(dict(x=9, y=9, z=9)).sel(x="x8", y="y8", z="z8").item() <= 1
        )

    def test_loc(self) -> None:
        """SparseDataArray.loc[] accessor works.

        For some version prior to sparse 0.11.2, a specific workaround was required, but
        no longer. Retain the test to catch any regression.
        """
        *_, x = add_test_data(Computer())

        # .loc accessor works, returns same class as object but 1 element
        assert isinstance(x.loc["foo1", 2040], SparseDataArray)
        assert isinstance(x.loc["foo1", 2040].item(), float)

    def test_scalar(self) -> None:
        """Scalar Quantities can be created."""
        A = Quantity(1.0, units="kg")
        B = Quantity(2.0, units="kg")

        # Fragment occurring in .operator.add()
        list(map(Quantity, xr.broadcast(*cast(xr.DataArray, (A, B)))))
