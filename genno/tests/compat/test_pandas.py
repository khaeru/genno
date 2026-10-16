import numpy as np
import pandas as pd
from pandas.core.algorithms import safe_sort


def test_safe_sort() -> None:
    """Test :func:`pandas.core.algorithms.safe_sort`.

    Internal pandas calls to this function crash pytest-xdist workers with Pandas 3.15
    on Windows. See https://github.com/pandas-dev/pandas/issues/71254.
    """
    values = np.array(["c", "a", "b"])
    result = safe_sort(values)
    # print(result)
    del result

    idx = pd.MultiIndex.from_product(
        [
            ["foo1", "foo2", "foo3", "bar4", "bar5", "bar6"],
            [2000, 2010, 2020, 2030, 2040, 2050],
        ],
        names=["t", "y"],
    )
    # print(idx)
    del idx
