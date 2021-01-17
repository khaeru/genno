import pandas as pd

from genno import Key, Quantity
from genno.testing import assert_logs
from genno.util import collect_units, filter_concat_args


def test_collect_units(ureg):
    q1 = Quantity(pd.Series([42, 43]), units="kg")
    # Force string units
    q1.attrs["_unit"] = "kg"

    # Units are converted to pint.Unit
    assert collect_units(q1) == [ureg.kg]


def test_filter_concat_args(caplog):
    with assert_logs(
        caplog,
        [
            "concat() argument 'key1' missing; will be omitted",
            "concat() argument <foo:x-y-z> missing; will be omitted",
        ],
    ):
        result = list(
            filter_concat_args(
                ["key1", Quantity(pd.Series([42, 43]), units="kg"), Key("foo", "xyz")]
            )
        )

    assert len(result) == 1
