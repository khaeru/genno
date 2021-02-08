import pandas as pd
import pytest
from dask.core import quote

from genno import Key, Quantity
from genno.testing import assert_logs
from genno.util import collect_units, filter_concat_args, unquote


def test_collect_units(ureg):
    q1 = Quantity(pd.Series([42, 43]), units="kg")
    # Force string units
    q1.attrs["_unit"] = "kg"

    # Units are converted to pint.Unit
    assert (ureg.kg,) == collect_units(q1)


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


@pytest.mark.parametrize(
    "value, exp",
    (
        # Quotable values are unwrapped
        (quote(dict(foo="bar")), dict(foo="bar")),
        (quote(["hello", "world"]), ["hello", "world"]),
        # No effect on others
        (42.0, 42.0),
    ),
)
def test_unquote(value, exp):
    assert exp == unquote(value)
