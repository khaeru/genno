import pandas as pd
import pytest

from genno import Computer, Quantity
from genno.core.sparsedataarray import SparseDataArray


@pytest.mark.usefixtures("parametrize_quantity_class")
def test_describe():
    c = Computer()
    c.add("foo", Quantity(pd.Series([42, 43])))

    if Quantity._get_class() is SparseDataArray:
        assert "\n".join(
            ["'foo':", "- <xarray.SparseDataArray (index: 2)>"]
        ) == c.describe("foo")
